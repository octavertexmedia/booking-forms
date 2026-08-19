# Cafe Orelo workshop portal — Handbook
> The one place that explains how this works. Plain English. Last updated: 2026-08-19

## 1. What it is
A public registration page for Cafe Orelo’s eggless tiramisu workshop. A guest books seats, pays on a unique Razorpay link, and only then gets the WhatsApp group invite. Kitchen staff edit the event in Wagtail and watch a participant list that matches the old Google Sheet.

## 2. How it works (the flow)
1. A guest opens the workshop page and submits name, WhatsApp, email, and seats.
2. The app writes a `PAYMENT_PENDING` row and asks Razorpay for a **new** Payment Link (never a shared URL).
3. The guest pays. Razorpay calls `/webhooks/razorpay/` with `payment_link.paid` (the return URL is a backup).
4. The row becomes `PAID`. The app sends the confirmation WhatsApp with the group invite link. The guest taps it and joins.
5. On the Saturday before the workshop, a scheduled command texts paid guests a reminder.

## 3. The parts
| Part | What it does | Where it lives |
|------|--------------|----------------|
| Public pages | Home + workshop form | Wagtail pages in `workshop/models.py`, templates in `workshop/templates/` |
| CMS | Edit date, price, copy, WhatsApp templates | Wagtail at `/admin/` |
| Participant list | The “sheet” | `Registration` model — Wagtail **Registrations** and `/django-admin/` CSV |
| Database | Pages + registrations | Neon Postgres (`DATABASE_URL`); SQLite if that is empty |
| Files | Hero images and collected CSS | AWS S3 via django-storages, or local `media/` |
| Payments | Unique Payment Links + webhook | `workshop/razorpay_client.py`, `/webhooks/razorpay/` |
| WhatsApp | Confirmation + reminder | `workshop/whatsapp.py` → VertexCRM / AI Sensy HTTP API |
| Serverless host | Request/response | **Vercel** Python (Django ASGI in `portal/asgi.py`) or AWS Lambda (`handler.py`, `template.yaml`) |

## 4. Run it locally
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py bootstrap_workshop
python manage.py runserver
```
Form: http://127.0.0.1:8000/tiramisu-workshop/ · Admin: http://127.0.0.1:8000/admin/

## 5. How it ships (deploy)
The live web app can ship on **Vercel** (`vercel.json`, `portal/asgi.py`) from the local tree with `vercel --prod`. Vercel auto-detects Django, runs `collectstatic`, and serves CSS from the CDN. Neon still holds data; S3 still holds media. Migrations are **not** run on every request — after you add Neon URLs, run them once against the **direct** URL (`DATABASE_URL_UNPOOLED`) from your laptop, then `bootstrap_workshop`. AWS Lambda (`Dockerfile` / `template.yaml`) remains an alternate host. The Saturday reminder is still a Lambda cron (`ReminderFunction`) until a Vercel Cron is added.

## 6. Data & integrations
- **Registration row:** timestamp, name, WhatsApp, email, seats, amount, payment link, payment id, status, group-invite sent, reference id.
- **Razorpay:** one Payment Link per row; webhook secret is used for `X-Razorpay-Signature` on the raw body.
- **WhatsApp:** we only send a link. We never add a number to a group.
- **Neon:** pooled URL for web traffic, unpooled URL for migrate.

## 7. Decisions & gotchas
- We replaced Google Form + Apps Script with Wagtail because the brief asked for a serverless Wagtail portal on Neon + S3. The guest-facing fields and payment rules are unchanged.
- We do X unique Payment Link per registration because Razorpay treats a link as one customer, and the spec forbids a shared URL.
- Watch out: webhook verification must hash the **raw** POST body. Do not re-serialize JSON.
- Watch out: `RAZORPAY_WEBHOOK_SECRET` is not the API key secret.
- Watch out: Lambda must use `CONN_MAX_AGE=0` and Neon’s `-pooler` host.
- Local demo uses `RAZORPAY_MOCK=true` so you can mark a payment paid without live keys.
- Public pages follow the **vibrant** client flyer, not HealthyOme and not the earlier muted tan/gold look: forest `#0B1F12`, lime `#A2D400`, magenta `#E2186A`, gold `#FFD54F`, take-home paper `#FFF6DC`, Playfair Display + Oswald + Great Vibes + Outfit. HealthyOme green stays on Wagtail/Django admin only (`admin.css`).
- The chef + tiramisu photo is cropped from the vibrant flyer (`workshop/static/workshop/images/chef-aanchal-tiramisu.png`). The full flyer sits beside it as `tiramisu-workshop-flyer.png`. Templates use the crop when no Wagtail `hero_image` is set.
- Take-home list, tagline, limited-seats line, and WhatsApp **7709818290** are template copy from the flyer. Date, time, venue, chef, and price still come from the Wagtail workshop page.
- Watch out: `bootstrap_workshop` refreshes those CMS fields to the flyer (23 Aug 2026, 3–5 PM, Aanchal Wadhwa, ₹1499). Do not re-run it after you have customized them in Wagtail.
- Octavertex Media credit is a shared partial (`workshop/partials/octavertex_credit.html`) on the public footer, Wagtail admin, and Django admin. On public pages the type is white and the logo is inverted so it reads on the dark green footer.

## 8. FAQ (for the tech team)
- **How do I change the workshop date or price?** Wagtail → Pages → Tiramisu Making Workshop. The public flyer layout will pick up date, time, venue, chef name, and price. Tagline, take-homes, and the enquiry WhatsApp number are in the templates.
- **How do I replace the chef photo?** Upload `hero_image` on the workshop page. Leave it blank to keep the cropped client flyer.
- **Where are secrets?** `.env` locally (never commit it). Vercel project environment variables in production (and Lambda if you still use SAM).
- **Why isn’t my change showing in production?** Confirm you redeployed on Vercel (`vercel --prod` from this folder) **and** ran migrate against Neon. Page edits live in the database, not the git repo. A deploy without `DATABASE_URL` can start, but workshop pages will be empty until Neon + `migrate` + `bootstrap_workshop`.
- **How do I export the sheet?** Django admin → Registrations → select rows → “Export sheet CSV”.
- **WhatsApp didn’t send?** Check `WHATSAPP_API_URL`. In production with a URL set, a failed POST leaves “Group invite sent” as NO so you can retry.
- **Where is the Octavertex credit?** Public footer on every page, Wagtail `/admin/` (dashboard + login), and Django `/django-admin/` footer.

## 9. Changelog
- 2026-08-19 — Vercel Python deploy: `vercel.json`, `.vercelignore`, and serverless settings that pick up `*.vercel.app`. Neon / S3 / Razorpay / WhatsApp still need project env vars.
- 2026-08-19 — Public UI rematched to the vibrant flyer: lime “Making Workshop”, magenta/gold price bar, saturated icon circles, Playfair wordmark, and a tighter chef crop. Admin chrome is still HealthyOme green.
- 2026-08-19 — Public home, workshop, and payment pages now match the Cafe Orelo flyer (forest/cream/gold, chef photo, take-homes, ₹1499, WhatsApp 7709818290). Admin chrome is still HealthyOme green.
- 2026-08-19 — First version: Wagtail form portal, Razorpay Payment Links, Neon/S3/Lambda wiring, confirmation + Saturday reminder.

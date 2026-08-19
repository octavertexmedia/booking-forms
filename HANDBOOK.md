# Cafe Orelo workshop portal — Handbook
> The one place that explains how this works. Plain English. Last updated: 2026-08-19

## 1. What it is
A booking portal for Cafe Orelo workshops. Each event is its own Wagtail page with its own form, price, seat cap, Razorpay Payment Links, WhatsApp group invite, and post-payment email. Kitchen staff add events in admin — not in code. The first live event is the eggless tiramisu workshop.

## 2. How it works (the flow)
1. A guest opens an event page (or picks one from Home when more than one is live) and submits name, WhatsApp, email, and seats.
2. The app writes a `PAYMENT_PENDING` row and asks Razorpay for a **new** Payment Link for **that event’s** amount (never a shared URL).
3. The guest pays. Razorpay calls `/webhooks/razorpay/` with `payment_link.paid` (the return URL is a backup).
4. The row becomes `PAID`. The app sends **WhatsApp and email**, both with that event’s group invite. The guest taps the link and joins. If email is not configured, payment still succeeds and the miss is logged.
5. On the Saturday before the workshop, a scheduled command texts paid guests a reminder.

## 3. The parts
| Part | What it does | Where it lives |
|------|--------------|----------------|
| Public pages | Home + workshop form | Wagtail pages in `workshop/models.py`, templates in `workshop/templates/` |
| CMS | Create/copy events; edit date, price, flyer, invites | Wagtail at `/admin/` — each **Event** page |
| Participant list | The “sheet”, filterable by event | `Registration` — Wagtail **Registrations** (CSV) and `/django-admin/` |
| Database | Pages + registrations | Neon Postgres (`DATABASE_URL`); SQLite if that is empty |
| Files | Hero images and collected CSS | AWS S3 via django-storages, or local `media/` |
| Payments | Unique Payment Links + webhook | `workshop/razorpay_client.py`, `/webhooks/razorpay/` |
| WhatsApp | Confirmation + reminder (per event) | `workshop/whatsapp.py` → VertexCRM / AI Sensy HTTP API |
| Email | Same group invite after payment | `workshop/email.py` → Django `send_mail` / SMTP |
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
- **Registration row:** timestamp, event, name, WhatsApp, email, seats, amount, payment link, payment id, status, WhatsApp-invite sent, email-invite sent, reference id.
- **Razorpay:** one Payment Link per row; description/notes include event title + reference; webhook secret is used for `X-Razorpay-Signature` on the raw body.
- **WhatsApp:** we only send that event’s invite link. We never add a number to a group.
- **Email:** same invite, using the event page’s subject + body. Needs `EMAIL_HOST` (or console locally). Missing config does not fail the webhook.
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
- Flyer title, tagline, gold banner, take-home list (one line per item), limited-seats line, enquiry WhatsApp, group invite, and post-payment email now live on the Event page. Defaults match the tiramisu flyer so `/tiramisu-workshop/` stays the same until someone edits it.
- Seat cap is per event. Only **PAID** seats count toward sold-out. Pending links do not hold a seat.
- Watch out: `bootstrap_workshop` refreshes those CMS fields to the flyer (23 Aug 2026, 3–5 PM, Aanchal Wadhwa, ₹1499). Do not re-run it after you have customized them in Wagtail.
- Watch out: `bootstrap_workshop` creates the superuser only if that username is missing. It does **not** reset the password on later runs. Local `.env` uses `DJANGO_SUPERUSER_PASSWORD=change-me`; Vercel does not set a superuser password. Production login is the Neon `auth_user` row, not the code default `admin12345`.
- Wagtail/Django admin chrome is Cafe Orelo + Octavertex (`admin.css`, `wagtailadmin` template overrides). The real Cafe Orelo wordmark (`cafe-orelo-logo.png`) sits on a cream plate so the dark olive mark reads on the forest sidebar. The Wagtail bird, “CO” mark, upgrade banner, and “Sign in to Wagtail” title are hidden/replaced.
- Public pages use the same real logo in the shared header (`base.html`), but **without** a cream pill: `filter: brightness(0) invert(1)` turns the dark olive PNG white on forest green (transparency stays). The “good food, good mood.” tagline stays. The chef/tiramisu photo is not the logo. Admin keeps the cream plate.
- Watch out: do not put `a:link { color: var(--ho-primary) }` on the whole admin. That green (`#4b8e3d`) on the forest sidebar (`#0b3f1f`) hid Registrations / Images / Documents until hover. Sidebar labels stay cream `#F5F5DC` by default.
- Watch out: the same green link rule on `#content a:link` painted “Add an image” and other header CTAs green-on-green. Button / `.w-btn` links are excluded; CTA labels stay white / cream `#F5F5DC` on the HealthyOme green button.
- Octavertex Media credit is a shared partial (`workshop/partials/octavertex_credit.html`) on the public footer, Wagtail admin, and Django admin. On public pages the type is white and the logo is inverted so it reads on the dark green footer.
- The booking form is a **cream ticket card** in the right column under the chef (`flyer-split--register`). It is a **grid sibling** of the photo, not inside `.flyer-visual`. Watch out: `.flyer-visual` uses `overflow: hidden` and `.flyer-portrait` uses `height: 100%` so a stretched right column will clip anything after the photo. Do not put the form back inside that well.

## 8. FAQ (for the tech team)
- **How do I add a second event?** Wagtail → Pages → Cafe Orelo → Add child page → **Event** (or copy Tiramisu Making Workshop). Set date, price, slug, WhatsApp group invite, and the email sent after payment. Publish. The booking URL is `/your-slug/`. Home shows cards once two or more events are live.
- **How do I change the workshop date or price?** Wagtail → Pages → that Event. Flyer copy, enquiry WhatsApp, group invite, and email are on the same page.
- **How do I replace the chef photo?** Upload `hero_image` on the workshop page. Leave it blank to keep the cropped client flyer.
- **Where are secrets?** `.env` locally (never commit it). Vercel project environment variables in production (and Lambda if you still use SAM).
- **Why isn’t my change showing in production?** Confirm you redeployed on Vercel (`vercel --prod` from this folder) **and** ran migrate against Neon. Page edits live in the database, not the git repo. A deploy without `DATABASE_URL` can start, but workshop pages will be empty until Neon + `migrate` + `bootstrap_workshop`.
- **How do I export the sheet?** Wagtail → Registrations → Download CSV (filter by event first). Or Django admin → Registrations → select rows → “Export sheet CSV”.
- **WhatsApp didn’t send?** Check `WHATSAPP_API_URL`. In production with a URL set, a failed POST leaves “WhatsApp invite sent” as NO so you can retry.
- **Email didn’t send?** Check `EMAIL_HOST` / `DEFAULT_FROM_EMAIL` on Vercel. Until SMTP is set, production uses a dummy backend: payment still works, “Email invite sent” stays NO (unless `RAZORPAY_MOCK=true`).
- **Where is the Octavertex credit?** Public footer on every page, Wagtail `/admin/` (dashboard + login), and Django `/django-admin/` footer.
- **Where is the booking form?** On `/tiramisu-workshop/`, in the right column under the chef (cream card: name, WhatsApp, email, seats). On a phone it sits **after** the flyer copy and price bar. The form is already in the HTML; if you only see a dark empty rectangle under the chef, the photo well is clipping it — not a missing env var.
- **Why isn’t my CSS change showing?** Public CSS is `{% static 'workshop/css/workshop.css' %}?v=…` (now `?v=20260819-logo-white`). Bump that query if Vercel or S3 serves a cached file. Admin CSS is `admin.css?v=…` from `wagtail_hooks.py`. This is not a Neon / `DATABASE_URL` issue.
- **Admin CTA labels look missing?** Header buttons such as “Add an image” are green. Labels must stay white / cream — never `--ho-primary` on a `.button` / `.w-btn`. Sidebar cream labels and the Cafe Orelo cream-plate logo are a separate rule.
- **Where is the Cafe Orelo logo on the public site?** Every public page header (`workshop/templates/workshop/base.html`). It is the real PNG, CSS-filtered to white (`brightness(0) invert(1)`) so the dark olive mark reads on forest green — no cream pill. Admin still uses a cream plate on the forest sidebar; do not share public classes with admin.
- **Admin sidebar items look missing?** They were green-on-green. Labels are cream by default now. The Cafe Orelo logo lives on a cream plate because the mark is dark olive.
- **Admin login failed with `admin` / `admin12345`?** That pair is only the bootstrap **code default**. The first production user was created from local `.env` (`change-me`) and bootstrap skipped later resets. Wagtail is `/admin/`. Django admin is `/django-admin/`. Reset the Neon user with `DATABASE_URL_UNPOOLED` and `portal.settings.serverless` — do not put the live password in this file.

## 9. Changelog
- 2026-08-19 — Public header logo: cream pill removed; dark olive PNG is filtered to white (`brightness(0) invert(1)`) on forest green (`workshop.css?v=20260819-logo-white`). Admin cream-plate logo left as-is.
- 2026-08-19 — Many events from Wagtail: reusable Event pages, Home cards when 2+ are live, per-event seat cap / WhatsApp invite / post-payment email, Registrations CSV + event filter. Tiramisu URL unchanged.
- 2026-08-19 — Wagtail admin CTAs (“Add an image”, `.button` / `.w-btn`) now use white / cream labels on the green button. `#content a:link` no longer paints button links `--ho-primary` (`admin.css?v=20260819-cta`). Sidebar cream labels and the Cafe Orelo cream-plate logo stay.
- 2026-08-19 — Public header now uses the real Cafe Orelo logo on a cream `#FFF6DC` pill (`base.html` + `workshop.css?v=20260819-events`) so the dark olive mark reads on forest green. Tagline kept. Admin logo work untouched.
- 2026-08-19 — Admin sidebar labels are cream on forest (green-on-green hid them until hover). Real Cafe Orelo logo on a cream plate; Wagtail upgrade banner off (`WAGTAIL_ENABLE_UPDATE_CHECK = False`).
- 2026-08-19 — Production admin password reset on Neon (bootstrap had left the local `.env` password). Wagtail bird/wordmark removed from admin login + sidebar; Cafe Orelo mark + Octavertex credit stay. CSRF also trusts `https://booking-forms-ten.vercel.app`.
- 2026-08-19 — Booking form is a cream card under the chef. It was in the HTML but clipped by the photo column’s `overflow: hidden` + `height: 100%` portrait (looked like an empty dark well).
- 2026-08-19 — Vercel Python deploy: `vercel.json`, `.vercelignore`, and serverless settings that pick up `*.vercel.app`. Neon / S3 / Razorpay / WhatsApp still need project env vars.
- 2026-08-19 — Public UI rematched to the vibrant flyer: lime “Making Workshop”, magenta/gold price bar, saturated icon circles, Playfair wordmark, and a tighter chef crop. Admin chrome is still HealthyOme green.
- 2026-08-19 — Public home, workshop, and payment pages now match the Cafe Orelo flyer (forest/cream/gold, chef photo, take-homes, ₹1499, WhatsApp 7709818290). Admin chrome is still HealthyOme green.
- 2026-08-19 — First version: Wagtail form portal, Razorpay Payment Links, Neon/S3/Lambda wiring, confirmation + Saturday reminder.

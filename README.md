# Cafe Orelo workshop portal
ok

Wagtail CMS registration portal for the Eggless Tiramisu Making Workshop. Guests register on the site, receive a unique Razorpay Payment Link, and get a WhatsApp confirmation (with the group invite) only after `payment_link.paid`.

Stack: **Django / Wagtail** (serverless-ready), **Neon Postgres**, **AWS S3** for media and static files, **AWS Lambda** via Mangum.

## What you get

- Public workshop page with the four spec fields (name, WhatsApp, email, seats)
- Unique Razorpay Payment Link per registration (`TIRAMISU-YYYYMMDD-00N`)
- Webhook + callback verification
- Participant list in Wagtail (`Registrations`) matching the spec sheet columns
- WhatsApp confirmation and a Saturday-evening reminder command
- CMS-editable date, copy, price, group invite, and message templates

## Local run

Use Python 3.12 (3.13 is fine). Python 3.14 may work but is not the pinned runtime.

```bash
cd "/Users/manishkumar/Registration Form"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — at minimum set DJANGO_SECRET_KEY and DJANGO_SUPERUSER_PASSWORD
python manage.py migrate
python manage.py bootstrap_workshop
python manage.py runserver
```

Open:

- Workshop form: http://127.0.0.1:8000/tiramisu-workshop/
- Wagtail admin: http://127.0.0.1:8000/admin/
- Django admin (CSV export): http://127.0.0.1:8000/django-admin/

With `RAZORPAY_MOCK=true` (the default in `.env.example`), submit the form and use **Mark as paid** to simulate the webhook.

## Required environment variables

See `.env.example` for the full list.

| Variable | Used for |
|---|---|
| `DJANGO_SECRET_KEY` | Django signing |
| `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` | Host + CSRF |
| `WAGTAILADMIN_BASE_URL` / `PUBLIC_BASE_URL` | Admin links + Razorpay callback |
| `DATABASE_URL` | Neon **pooled** URL (`-pooler`) at runtime |
| `DATABASE_URL_UNPOOLED` | Neon **direct** URL for `migrate` |
| `AWS_STORAGE_BUCKET_NAME` (+ region / keys) | S3 media + static |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Payment Links |
| `RAZORPAY_WEBHOOK_SECRET` | `X-Razorpay-Signature` on `/webhooks/razorpay/` |
| `WHATSAPP_API_URL` / `WHATSAPP_API_TOKEN` | VertexCRM / AI Sensy HTTP send |

Leave `DATABASE_URL` empty to use SQLite for a local demo. Leave `AWS_STORAGE_BUCKET_NAME` empty to store uploads on disk.

### Neon

1. Create a Neon project (Vercel Neon integration is fine).
2. Copy the pooled connection string into `DATABASE_URL`.
3. Copy the direct connection string into `DATABASE_URL_UNPOOLED`.
4. Run migrations against the **direct** URL:

```bash
DATABASE_URL="$DATABASE_URL_UNPOOLED" python manage.py migrate
```

Runtime (Lambda / `runserver` with Neon) should keep using the pooled URL. `CONN_MAX_AGE` is `0` so serverless workers do not hold connections.

### AWS S3

Create a bucket (region e.g. `ap-south-1`). Allow public read on `static/*` and `media/*`, or put CloudFront in front and set `AWS_S3_CUSTOM_DOMAIN`.

Then:

```bash
python manage.py collectstatic --noinput
```

Workshop hero images uploaded in Wagtail go to `s3://$BUCKET/media/`.

### Razorpay

1. Confirm Payment Links are enabled on the account.
2. Create a webhook pointing at `https://YOUR_DOMAIN/webhooks/razorpay/`.
3. Subscribe to **`payment_link.paid`**.
4. Put the webhook secret in `RAZORPAY_WEBHOOK_SECRET` (this is not the API key secret).
5. Set `RAZORPAY_MOCK=false` in production.

### WhatsApp (VertexCRM / AI Sensy)

After payment the portal POSTs JSON to `WHATSAPP_API_URL`:

```json
{
  "to": "+91XXXXXXXXXX",
  "message": "…confirmation or reminder text…",
  "name": "Rahul",
  "template": "registration_confirmed"
}
```

If the provider needs extra keys, put them in `WHATSAPP_EXTRA_PAYLOAD` as JSON. The group invite is a link the guest taps themselves — the app never force-adds anyone to WhatsApp.

If `WHATSAPP_API_URL` is empty in debug/mock mode, the message is logged and the sheet column is still marked sent so you can demo locally.

## Serverless deploy (AWS Lambda)

The app is ASGI, wrapped by Mangum in `handler.py`. `template.yaml` builds a container image (Wagtail is too large for a slim zip).

1. Create the Neon project, S3 bucket, and Razorpay webhook as above.
2. Put production secrets in Lambda environment variables (or SSM — wire them before first traffic).
3. Run migrations once against `DATABASE_URL_UNPOOLED` from your laptop or a one-off task.
4. Deploy:

```bash
sam build
sam deploy --guided
```

5. Set `PUBLIC_BASE_URL` and `WAGTAILADMIN_BASE_URL` to the HTTP API URL (or your custom domain).
6. Add that host to `DJANGO_ALLOWED_HOSTS` and `https://…` to `DJANGO_CSRF_TRUSTED_ORIGINS`.

`ReminderFunction` runs `send_workshop_reminders` every Saturday at 18:00 IST (`cron(30 12 ? * SAT *)` UTC). It only messages **PAID** guests whose workshop is tomorrow.

Manual reminder:

```bash
python manage.py send_workshop_reminders
python manage.py send_workshop_reminders --force
```

## CMS notes

Each live **Event** page is its own booking form. Add or copy an event under **Pages → Cafe Orelo**. Edit date, price, seat cap, flyer copy, WhatsApp group invite, and the post-payment email on that page. Placeholders: `{{name}}`, `{{event}}`, `{{group_invite_link}}`, `{{invite_link}}`, `{{amount}}`, `{{date}}`, `{{time}}`, `{{venue}}`, `{{chef}}`, `{{reference}}`, `{{seats}}`. Export the sheet from **Registrations** (CSV) or Django admin.

## Defaults chosen where the spec was silent

- Indian (+91) WhatsApp numbers only
- WhatsApp provider is a generic HTTPS POST (VertexCRM/AI Sensy payloads differ; adjust `WHATSAPP_EXTRA_PAYLOAD`)
- Database search backend (no Elasticsearch) so Lambda stays small
- Saturday reminder is “workshop is tomorrow”, not a hard-coded clock check inside the web request

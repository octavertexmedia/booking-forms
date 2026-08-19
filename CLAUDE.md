# Cafe Orelo workshop portal

Wagtail/Django registration portal for Cafe Orelo’s tiramisu workshop: form → unique Razorpay Payment Link → webhook → WhatsApp invite. Neon Postgres, S3 media, Lambda/Mangum for serverless.

## Stack + skills

- **Django / Wagtail 6.4** — `workshop` app (pages, registrations, webhooks)
- **Neon Postgres** — neon / neon-postgres skills (`DATABASE_URL` pooled, `DATABASE_URL_UNPOOLED` for migrate)
- **UI** — frontend-design, ui-ux-pro-max (public templates + `workshop/static/workshop/css/workshop.css`)
- **Docs** — project-handbook (`HANDBOOK.md`)

## Standing rules

- After building or changing a feature, update `HANDBOOK.md` (project-handbook skill) and add a changelog line.
- Verify UI/behaviour changes with the `playwright` MCP (drive the real flow, don’t just typecheck).
- Check library APIs via `context7` instead of guessing.
- Token efficiency: no broad scans, no re-reads, tight tool calls.
- Record durable project facts to the `memory` graph.
- If this repo deploys from a *different* remote than it's edited in, FLAG before assuming an edit reaches prod.

## Gotchas

- Spec source of truth: `context.txt`. Do not add features the spec did not ask for.
- Webhook signature = HMAC-SHA256 of the **raw** body with `RAZORPAY_WEBHOOK_SECRET`.
- Never force-add guests to WhatsApp; only send the invite link after `PAID`.
- Serverless: `portal.settings.serverless`, `handler.handler`, `CONN_MAX_AGE=0`, files on S3.

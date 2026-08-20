"""Post-payment and reminder email via Zoho SMTP (HTTP fallback if configured)."""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail

from .messaging import render_template
from .models import Registration

logger = logging.getLogger(__name__)


def email_is_configured() -> bool:
    if getattr(settings, "EMAIL_HTTP_URL", ""):
        return True
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if backend.endswith("dummy.EmailBackend"):
        return False
    if backend.endswith("smtp.EmailBackend") and not getattr(settings, "EMAIL_HOST", ""):
        return False
    return bool(backend)


def _log_only_counts_as_sent() -> bool:
    return (not email_is_configured()) and (settings.DEBUG or settings.RAZORPAY_MOCK)


def _send_via_http(subject: str, body: str, to: str) -> bool:
    url = getattr(settings, "EMAIL_HTTP_URL", "") or ""
    if not url:
        return False
    headers = {"Content-Type": "application/json"}
    token = getattr(settings, "EMAIL_HTTP_TOKEN", "") or ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.post(
        url,
        json={
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "text": body,
        },
        headers=headers,
        timeout=20,
    )
    if response.status_code >= 400:
        logger.error("HTTP email fallback failed (%s): %s", response.status_code, response.text[:300])
        return False
    return True


def _deliver(subject: str, body: str, to: str, reference_id: str) -> bool:
    if not email_is_configured():
        logger.info(
            "Email not configured; skipping mail for %s\nSubject: %s\n%s",
            reference_id,
            subject,
            body,
        )
        return _log_only_counts_as_sent()

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
        logger.info("SMTP email sent to %s for %s", to, reference_id)
        return True
    except Exception:
        logger.exception("SMTP email failed for %s", reference_id)
        if getattr(settings, "EMAIL_HTTP_URL", ""):
            try:
                if _send_via_http(subject, body, to):
                    logger.info("HTTP email fallback sent to %s for %s", to, reference_id)
                    return True
            except Exception:
                logger.exception("HTTP email fallback failed for %s", reference_id)
        return False


def send_invite_email(registration: Registration) -> bool:
    workshop = registration.workshop
    subject = render_template(workshop.email_subject, workshop, registration).replace("\n", " ")
    body = render_template(workshop.email_body, workshop, registration)
    if not _deliver(subject, body, registration.email, registration.reference_id):
        return False
    registration.email_invite_sent = True
    registration.save(update_fields=["email_invite_sent"])
    return True


def send_reminder_email(registration: Registration) -> bool:
    workshop = registration.workshop
    subject = render_template(workshop.reminder_email_subject, workshop, registration).replace(
        "\n", " "
    )
    body = render_template(workshop.reminder_template, workshop, registration)
    return _deliver(subject, body, registration.email, registration.reference_id)

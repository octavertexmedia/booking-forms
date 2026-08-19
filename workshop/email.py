"""Post-payment email with the event’s WhatsApp group invite."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from .messaging import render_template
from .models import Registration

logger = logging.getLogger(__name__)


def email_is_configured() -> bool:
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if backend.endswith("dummy.EmailBackend"):
        return False
    if backend.endswith("smtp.EmailBackend") and not getattr(settings, "EMAIL_HOST", ""):
        return False
    return bool(backend)


def _log_only_counts_as_sent() -> bool:
    return (not email_is_configured()) and (settings.DEBUG or settings.RAZORPAY_MOCK)


def send_invite_email(registration: Registration) -> bool:
    workshop = registration.workshop
    subject = render_template(workshop.email_subject, workshop, registration).replace("\n", " ")
    body = render_template(workshop.email_body, workshop, registration)

    if not email_is_configured():
        logger.info(
            "Email not configured; skipping invite email for %s\nSubject: %s\n%s",
            registration.reference_id,
            subject,
            body,
        )
        if _log_only_counts_as_sent():
            registration.email_invite_sent = True
            registration.save(update_fields=["email_invite_sent"])
            return True
        return False

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[registration.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Email send failed for %s", registration.reference_id)
        return False

    registration.email_invite_sent = True
    registration.save(update_fields=["email_invite_sent"])
    return True

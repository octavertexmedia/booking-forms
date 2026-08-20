"""Paid-guest reminders: email + WhatsApp, driven by each Event's hours-before window."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.utils import timezone

from .email import send_reminder_email
from .models import Registration, RegistrationStatus, WorkshopPage
from .whatsapp import send_reminder

logger = logging.getLogger(__name__)


def event_starts_at(workshop: WorkshopPage):
    naive = datetime.combine(workshop.workshop_date, workshop.start_time)
    tz = timezone.get_current_timezone()
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, tz)
    return naive


def reminder_is_due(workshop: WorkshopPage, now=None) -> bool:
    now = now or timezone.now()
    starts = event_starts_at(workshop)
    hours = int(workshop.reminder_hours_before or 24)
    window_start = starts - timedelta(hours=hours)
    return window_start <= now < starts


def send_registration_reminder(registration: Registration) -> bool:
    """Send WhatsApp + email reminder. Mark sent if either channel succeeds."""
    wa_ok = False
    email_ok = False
    try:
        wa_ok = bool(send_reminder(registration))
    except Exception:
        logger.exception("Reminder WhatsApp failed for %s", registration.reference_id)
    try:
        email_ok = bool(send_reminder_email(registration))
    except Exception:
        logger.exception("Reminder email failed for %s", registration.reference_id)
    if wa_ok or email_ok:
        registration.reminder_sent = True
        registration.save(update_fields=["reminder_sent"])
        logger.info(
            "Reminder sent for %s (whatsapp=%s email=%s)",
            registration.reference_id,
            wa_ok,
            email_ok,
        )
        return True
    logger.warning("Reminder not delivered for %s", registration.reference_id)
    return False


def send_due_reminders(*, force: bool = False) -> dict:
    qs = Registration.objects.filter(
        status=RegistrationStatus.PAID,
        reminder_sent=False,
    ).select_related("workshop")
    sent = 0
    skipped = 0
    considered = 0
    for registration in qs:
        workshop = registration.workshop
        if not force and not reminder_is_due(workshop):
            skipped += 1
            continue
        considered += 1
        if send_registration_reminder(registration):
            sent += 1
        else:
            skipped += 1
    result = {"ok": True, "sent": sent, "skipped": skipped, "considered": considered}
    logger.info("Reminders run: %s", result)
    return result

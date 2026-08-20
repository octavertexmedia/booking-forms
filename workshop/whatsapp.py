"""Send WhatsApp text via VertexCRM / AI Sensy HTTP API, or log if unconfigured."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings

from .messaging import render_template
from .models import Registration

logger = logging.getLogger(__name__)


def send_whatsapp(to: str, message: str, extra: dict[str, Any] | None = None) -> bool:
    url = settings.WHATSAPP_API_URL
    if not url:
        logger.info("WhatsApp API URL unset; logging message for %s\n%s", to, message)
        return False

    payload: dict[str, Any] = {
        "to": f"+91{to}" if len(to) == 10 else to,
        "message": message,
    }
    if extra:
        payload.update(extra)
    try:
        configured = json.loads(settings.WHATSAPP_EXTRA_PAYLOAD or "{}")
        if isinstance(configured, dict):
            payload.update(configured)
    except json.JSONDecodeError:
        logger.warning("WHATSAPP_EXTRA_PAYLOAD is not valid JSON; ignoring.")

    headers = {"Content-Type": "application/json"}
    if settings.WHATSAPP_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.WHATSAPP_API_TOKEN}"

    response = requests.post(url, json=payload, headers=headers, timeout=20)
    if response.status_code >= 400:
        logger.error("WhatsApp send failed (%s): %s", response.status_code, response.text)
        return False
    return True


def send_confirmation(registration: Registration) -> bool:
    workshop = registration.workshop
    message = render_template(workshop.confirmation_template, workshop, registration)
    sent = send_whatsapp(
        registration.whatsapp,
        message,
        extra={"name": registration.full_name, "template": "registration_confirmed"},
    )
    if sent or _log_only_counts_as_sent():
        registration.group_invite_sent = True
        registration.save(update_fields=["group_invite_sent"])
        return True
    return False


def send_reminder(registration: Registration) -> bool:
    """Send the WhatsApp reminder. Does not flip reminder_sent — callers own that flag."""
    workshop = registration.workshop
    message = render_template(workshop.reminder_template, workshop, registration)
    sent = send_whatsapp(
        registration.whatsapp,
        message,
        extra={"name": registration.full_name, "template": "workshop_reminder"},
    )
    return bool(sent or _log_only_counts_as_sent())


def _log_only_counts_as_sent() -> bool:
    return not settings.WHATSAPP_API_URL and (settings.DEBUG or settings.RAZORPAY_MOCK)

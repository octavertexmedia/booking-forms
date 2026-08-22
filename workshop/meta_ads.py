"""Meta Pixel + Conversions API. Purchase fires only after confirm_paid."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings

from .models import Registration

logger = logging.getLogger(__name__)

GRAPH_VERSION = "v21.0"


def pixel_id() -> str:
    return (getattr(settings, "META_PIXEL_ID", "") or "").strip()


def capi_token() -> str:
    return (getattr(settings, "META_CAPI_ACCESS_TOKEN", "") or "").strip()


def domain_verification() -> str:
    return (getattr(settings, "META_DOMAIN_VERIFICATION", "") or "").strip()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _user_data(registration: Registration) -> dict:
    data: dict[str, str] = {}
    email = (registration.email or "").strip().lower()
    if email:
        data["em"] = _sha256(email)
    digits = "".join(ch for ch in (registration.whatsapp or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) >= 12:
        phone = digits[-12:]
    elif len(digits) >= 10:
        phone = f"91{digits[-10:]}"
    else:
        phone = ""
    if phone:
        data["ph"] = _sha256(phone)
    country = (getattr(settings, "META_USER_COUNTRY", "") or "in").strip().lower()
    if country:
        data["country"] = _sha256(country)
    return data


def _custom_data(registration: Registration) -> dict:
    workshop = registration.workshop
    name = ""
    if workshop:
        name = (workshop.workshop_subtitle or workshop.title or "").strip()
    amount = registration.amount if registration.amount is not None else Decimal("0")
    return {
        "currency": "INR",
        "value": float(amount),
        "content_name": name or "Cafe Orelo workshop",
        "content_type": "product",
        "content_ids": [registration.reference_id],
        "num_items": int(registration.seats or 1),
        "order_id": registration.reference_id,
    }


def purchase_event_id(registration: Registration) -> str:
    return f"purchase-{registration.reference_id}"


def send_capi_purchase(registration: Registration) -> None:
    """Server Purchase so Meta can optimize even if the guest never returns from Razorpay."""
    pixel = pixel_id()
    token = capi_token()
    if not pixel or not token:
        return
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "https://bookings.healthyome.in").rstrip(
        "/"
    )
    payload = {
        "data": [
            {
                "event_name": "Purchase",
                "event_time": int(time.time()),
                "event_id": purchase_event_id(registration),
                "event_source_url": f"{base}/payments/status/{registration.reference_id}/",
                "action_source": "website",
                "user_data": _user_data(registration),
                "custom_data": _custom_data(registration),
            }
        ],
        "access_token": token,
    }
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{pixel}/events"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read().decode("utf-8", errors="replace")
        logger.info("Meta CAPI Purchase sent for %s: %s", registration.reference_id, body[:200])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        logger.exception(
            "Meta CAPI Purchase failed for %s: %s %s",
            registration.reference_id,
            exc.code,
            detail,
        )
    except Exception:
        logger.exception("Meta CAPI Purchase failed for %s", registration.reference_id)

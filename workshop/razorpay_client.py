"""Razorpay Payment Links — one unique link per registration, as the spec requires."""

from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings


class RazorpayError(Exception):
    pass


@dataclass
class PaymentLink:
    id: str
    url: str
    raw: dict[str, Any]


def has_api_keys() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def _auth() -> tuple[str, str]:
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET
    if not key_id or not key_secret:
        raise RazorpayError("Razorpay keys are not configured.")
    return key_id, key_secret


def create_payment_link(
    *,
    amount_paise: int,
    description: str,
    name: str,
    email: str,
    contact: str,
    reference_id: str,
    callback_url: str,
    notes: dict[str, str] | None = None,
) -> PaymentLink:
    if settings.RAZORPAY_MOCK:
        fake_id = f"plink_mock_{reference_id}"
        return PaymentLink(
            id=fake_id,
            url=f"{settings.PUBLIC_BASE_URL}/payments/mock/{reference_id}/",
            raw={"id": fake_id, "short_url": "mock"},
        )

    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description,
        "customer": {
            "name": name,
            "email": email,
            "contact": contact,
        },
        "notify": {"sms": True, "email": True},
        "reminder_enable": True,
        "reference_id": reference_id,
        "callback_url": callback_url,
        "callback_method": "get",
        "notes": notes or {},
    }
    response = requests.post(
        "https://api.razorpay.com/v1/payment_links",
        json=payload,
        auth=_auth(),
        timeout=20,
    )
    if response.status_code >= 400:
        existing = fetch_payment_link_by_reference(reference_id)
        url = existing.get("short_url") or existing.get("url")
        if existing.get("id") and url:
            return PaymentLink(id=str(existing["id"]), url=str(url), raw=existing)
        raise RazorpayError(f"Razorpay rejected the payment link: {response.text}")
    data = response.json()
    url = data.get("short_url") or data.get("url")
    if not url or not data.get("id"):
        raise RazorpayError("Razorpay response was missing a payment link.")
    return PaymentLink(id=data["id"], url=url, raw=data)


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def callback_secrets() -> list[str]:
    """Secrets that may verify a Payment Link return (key secret, then webhook)."""
    secrets: list[str] = []
    for value in (
        settings.RAZORPAY_KEY_SECRET,
        settings.RAZORPAY_WEBHOOK_SECRET,
    ):
        if value and value not in secrets:
            secrets.append(value)
    return secrets


def fetch_payment(payment_id: str) -> dict[str, Any]:
    """Load a payment from Razorpay so we can match email / phone / status."""
    if settings.RAZORPAY_MOCK or not payment_id or not has_api_keys():
        return {}
    try:
        response = requests.get(
            f"https://api.razorpay.com/v1/payments/{payment_id}",
            auth=_auth(),
            timeout=15,
        )
    except requests.RequestException:
        return {}
    if response.status_code >= 400:
        return {}
    data = response.json()
    return data if isinstance(data, dict) else {}


def fetch_payment_link(link_id: str) -> dict[str, Any]:
    """Load a Payment Link (status + payments) from Razorpay."""
    if settings.RAZORPAY_MOCK or not link_id or not has_api_keys():
        return {}
    try:
        response = requests.get(
            f"https://api.razorpay.com/v1/payment_links/{link_id}",
            auth=_auth(),
            timeout=15,
        )
    except requests.RequestException:
        return {}
    if response.status_code >= 400:
        return {}
    data = response.json()
    return data if isinstance(data, dict) else {}


def fetch_payment_link_by_reference(reference_id: str) -> dict[str, Any]:
    """Find a Payment Link by our booking reference_id."""
    if settings.RAZORPAY_MOCK or not reference_id or not has_api_keys():
        return {}
    try:
        response = requests.get(
            "https://api.razorpay.com/v1/payment_links",
            params={"reference_id": reference_id},
            auth=_auth(),
            timeout=15,
        )
    except requests.RequestException:
        return {}
    if response.status_code >= 400:
        return {}
    data = response.json()
    items = data.get("payment_links") if isinstance(data, dict) else None
    if isinstance(items, list) and items:
        first = items[0]
        return first if isinstance(first, dict) else {}
    return {}


def payment_link_paid_info(data: dict[str, Any]) -> tuple[bool, str]:
    """Return (is_paid, payment_id) from a Payment Link API payload."""
    if not isinstance(data, dict) or not data:
        return False, ""
    status = str(data.get("status") or "").strip().lower()
    payment_id = ""
    payments = data.get("payments")
    if isinstance(payments, list):
        for item in payments:
            if not isinstance(item, dict):
                continue
            item_status = str(item.get("status") or "").strip().lower()
            item_id = str(item.get("payment_id") or item.get("id") or "").strip()
            if item_status in {"captured", "authorized", "paid"} and item_id:
                return True, item_id
            if item_id and not payment_id:
                payment_id = item_id
    if status == "paid":
        return True, payment_id
    return False, payment_id


def verify_callback_signature(
    *,
    payment_link_id: str,
    payment_link_reference_id: str,
    payment_link_status: str,
    payment_id: str,
    signature: str,
) -> bool:
    if settings.RAZORPAY_MOCK:
        return True
    secrets = callback_secrets()
    if not secrets:
        return True
    if not signature:
        return False
    message = "|".join(
        [payment_link_id, payment_link_reference_id, payment_link_status, payment_id]
    )
    encoded = message.encode("utf-8")
    for secret in secrets:
        expected = hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature):
            return True
    return False

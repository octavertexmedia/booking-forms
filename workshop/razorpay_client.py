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
    secret = settings.RAZORPAY_KEY_SECRET
    if not secret or not signature:
        return False
    message = "|".join(
        [payment_link_id, payment_link_reference_id, payment_link_status, payment_id]
    )
    expected = hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

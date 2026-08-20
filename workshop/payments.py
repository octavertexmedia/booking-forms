"""Mark a registration PAID and send the post-payment invites (email + WhatsApp)."""

from __future__ import annotations

import logging
import re
from typing import Any

from .email import send_invite_email
from .models import Registration, RegistrationStatus
from .whatsapp import send_confirmation

logger = logging.getLogger(__name__)

REFERENCE_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,24}-\d{8}-\d{2,})\b")
PAID_EVENTS = frozenset(
    {
        "payment_link.paid",
        "payment.captured",
        "payment.authorized",
        "order.paid",
    }
)


def last10(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if digits else ""


def payload_entity(payload: dict, key: str) -> dict:
    entity = payload.get("payload", {}).get(key, {}).get("entity") or {}
    return entity if isinstance(entity, dict) else {}


def _walk_strings(value: Any, into: list[str], depth: int = 0) -> None:
    if depth > 6:
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            into.append(text)
        return
    if isinstance(value, dict):
        for item in value.values():
            _walk_strings(item, into, depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _walk_strings(item, into, depth + 1)


def _notes(entity: dict) -> dict:
    notes = entity.get("notes") or {}
    return notes if isinstance(notes, dict) else {}


def _collect_reference_candidates(payload: dict) -> list[str]:
    refs: list[str] = []
    link = payload_entity(payload, "payment_link")
    payment = payload_entity(payload, "payment")
    order = payload_entity(payload, "order")
    for entity in (link, payment, order):
        for key in ("reference_id", "reference", "receipt"):
            raw = str(entity.get(key) or "").strip()
            if raw:
                refs.append(raw)
        notes = _notes(entity)
        for key in ("reference", "reference_id", "booking_ref", "ref"):
            raw = str(notes.get(key) or "").strip()
            if raw:
                refs.append(raw)
    strings: list[str] = []
    _walk_strings(payload, strings)
    for text in strings:
        refs.extend(REFERENCE_RE.findall(text))
    seen: set[str] = set()
    unique: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            unique.append(ref)
    return unique


def _collect_ids(payload: dict) -> tuple[str, str, str]:
    link = payload_entity(payload, "payment_link")
    payment = payload_entity(payload, "payment")
    order = payload_entity(payload, "order")
    notes = {}
    notes.update(_notes(order))
    notes.update(_notes(payment))
    notes.update(_notes(link))
    payment_link_id = str(link.get("id") or notes.get("payment_link_id") or "")
    registration_pk = str(notes.get("registration_id") or "").strip()
    slug = str(
        notes.get("workshop") or notes.get("event_slug") or notes.get("event") or ""
    ).strip()
    return payment_link_id, registration_pk, slug


def _collect_contact(payload: dict) -> tuple[str, str]:
    payment = payload_entity(payload, "payment")
    link = payload_entity(payload, "payment_link")
    order = payload_entity(payload, "order")
    customer = link.get("customer") if isinstance(link.get("customer"), dict) else {}
    notes = {}
    notes.update(_notes(order))
    notes.update(_notes(payment))
    notes.update(_notes(link))
    email = str(
        payment.get("email")
        or customer.get("email")
        or notes.get("email")
        or ""
    ).strip().lower()
    contact = str(
        payment.get("contact")
        or customer.get("contact")
        or notes.get("contact")
        or notes.get("whatsapp")
        or notes.get("phone")
        or ""
    )
    return email, last10(contact)


def _pending_for_event(slug: str):
    pending = Registration.objects.filter(
        status=RegistrationStatus.PAYMENT_PENDING
    ).select_related("workshop", "package")
    if slug:
        pending = pending.filter(workshop__slug=slug)
    return pending


def match_registration(payload: dict) -> Registration | None:
    """Resolve a Razorpay payload to one registration.

    Order: reference / TIRAMISU-… id → payment-link id → row pk → email →
    WhatsApp last 10. Prefer a unique PENDING row for that event.
    """
    payment_link_id, registration_pk, slug = _collect_ids(payload)
    payment = payload_entity(payload, "payment")
    amount = payment.get("amount")
    if amount is None:
        amount = payload_entity(payload, "order").get("amount")

    for ref in _collect_reference_candidates(payload):
        found = Registration.objects.filter(reference_id=ref).first()
        if found:
            logger.info("Webhook matched %s by reference", found.reference_id)
            return found

    if payment_link_id:
        found = Registration.objects.filter(payment_link_id=payment_link_id).first()
        if found:
            logger.info("Webhook matched %s by payment_link_id", found.reference_id)
            return found

    if registration_pk.isdigit():
        found = Registration.objects.filter(pk=int(registration_pk)).first()
        if found:
            logger.info("Webhook matched %s by registration pk", found.reference_id)
            return found

    email, phone = _collect_contact(payload)
    pending = list(_pending_for_event(slug))
    if not pending and slug:
        pending = list(_pending_for_event(""))

    email_hits = [
        row for row in pending if email and row.email.lower() == email
    ]
    phone_hits = [
        row for row in pending if phone and last10(row.whatsapp) == phone
    ]

    def _unique(rows: list[Registration], how: str) -> Registration | None:
        if len(rows) == 1:
            logger.info("Webhook matched %s by %s", rows[0].reference_id, how)
            return rows[0]
        if isinstance(amount, int) and len(rows) > 1:
            by_amount = [row for row in rows if row.amount_paise == amount]
            if len(by_amount) == 1:
                logger.info(
                    "Webhook matched %s by %s + amount",
                    by_amount[0].reference_id,
                    how,
                )
                return by_amount[0]
        if rows:
            logger.warning(
                "Webhook %s matched %s PENDING rows (email=%s phone=%s slug=%s)",
                how,
                len(rows),
                email or "—",
                phone or "—",
                slug or "—",
            )
        return None

    both = [row for row in email_hits if row in phone_hits]
    matched = _unique(both, "email+phone")
    if matched:
        return matched
    matched = _unique(email_hits, "email")
    if matched:
        return matched
    return _unique(phone_hits, "whatsapp")


def match_from_callback(
    *,
    reference_id: str = "",
    payment_link_id: str = "",
    payment_id: str = "",
    email: str = "",
    contact: str = "",
    notes: dict | None = None,
) -> Registration | None:
    """Resolve a Payment Link return (query/form fields, not a webhook envelope)."""
    extra = notes if isinstance(notes, dict) else {}
    payload = {
        "payload": {
            "payment_link": {
                "entity": {
                    "id": payment_link_id,
                    "reference_id": reference_id,
                    "customer": {"email": email, "contact": contact},
                    "notes": extra,
                }
            },
            "payment": {
                "entity": {
                    "id": payment_id,
                    "email": email,
                    "contact": contact,
                    "notes": extra,
                }
            },
        }
    }
    return match_registration(payload)


def deliver_invites(registration: Registration) -> None:
    """WhatsApp + email with this event's group invite. Failures must not fail payment."""
    registration.refresh_from_db()
    if not registration.group_invite_sent:
        try:
            send_confirmation(registration)
        except Exception:
            logger.exception("WhatsApp confirmation failed for %s", registration.reference_id)
    registration.refresh_from_db()
    if not registration.email_invite_sent:
        try:
            send_invite_email(registration)
        except Exception:
            logger.exception("Invite email failed for %s", registration.reference_id)


def confirm_paid(
    registration: Registration,
    payment_id: str = "",
    raw: dict | None = None,
) -> Registration:
    """Set PAID, store payment id, then send invites once. Idempotent."""
    already_paid = registration.status == RegistrationStatus.PAID
    fields = ["status"]
    registration.status = RegistrationStatus.PAID
    if payment_id:
        registration.payment_id = payment_id
        fields.append("payment_id")
    if raw is not None:
        registration.raw_webhook = raw
        fields.append("raw_webhook")
    Registration.objects.filter(pk=registration.pk).update(
        **{name: getattr(registration, name) for name in fields}
    )
    registration.refresh_from_db()
    if already_paid and registration.group_invite_sent and registration.email_invite_sent:
        logger.info("Already PAID and invites sent for %s — skip", registration.reference_id)
        return registration
    logger.info(
        "confirm_paid %s payment_id=%s already_paid=%s email_sent=%s wa_sent=%s",
        registration.reference_id,
        payment_id or "—",
        already_paid,
        registration.email_invite_sent,
        registration.group_invite_sent,
    )
    deliver_invites(registration)
    registration.refresh_from_db()
    return registration

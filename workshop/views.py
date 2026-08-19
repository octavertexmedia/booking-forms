from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .email import send_invite_email
from .forms import RegistrationForm
from .models import Registration, RegistrationStatus, WorkshopPage
from .razorpay_client import (
    RazorpayError,
    create_payment_link,
    verify_callback_signature,
    verify_webhook_signature,
)
from .whatsapp import send_confirmation

logger = logging.getLogger(__name__)


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True, "service": "cafe-orelo-workshop"})


def _deliver_invites(registration: Registration) -> None:
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


def _mark_paid(registration: Registration, payment_id: str, raw: dict | None = None) -> None:
    already_paid = registration.status == RegistrationStatus.PAID
    registration.status = RegistrationStatus.PAID
    if payment_id:
        registration.payment_id = payment_id
    if raw is not None:
        registration.raw_webhook = raw
    registration.save(update_fields=["status", "payment_id", "raw_webhook"])
    if already_paid and registration.group_invite_sent and registration.email_invite_sent:
        return
    _deliver_invites(registration)


def register(request: HttpRequest, page: WorkshopPage):
    form = RegistrationForm(page, request.POST or None)
    if request.method != "POST":
        return {"form": form}

    if not form.is_valid():
        return {"form": form}

    data = form.cleaned_data
    amount = page.price_per_seat * data["seats"]

    registration = None
    for _attempt in range(3):
        try:
            with transaction.atomic():
                locked = WorkshopPage.objects.select_for_update().get(pk=page.pk)
                remaining = locked.seats_remaining()
                if data["seats"] > remaining:
                    if remaining <= 0:
                        form.add_error(None, "This event is sold out.")
                    else:
                        form.add_error(
                            "seats",
                            f"Only {remaining} seat{'s' if remaining != 1 else ''} left for this event.",
                        )
                    return {"form": form}
                registration = Registration.objects.create(
                    workshop=locked,
                    full_name=data["full_name"],
                    whatsapp=data["whatsapp"],
                    email=data["email"],
                    seats=data["seats"],
                    amount=amount,
                    reference_id=locked.next_reference_id(),
                    status=RegistrationStatus.PAYMENT_PENDING,
                )
            break
        except IntegrityError:
            registration = None
    if registration is None:
        form.add_error(None, "We could not hold that reservation. Please try again.")
        return {"form": form}

    callback_url = f"{settings.PUBLIC_BASE_URL}/payments/callback/"
    try:
        link = create_payment_link(
            amount_paise=registration.amount_paise,
            description=page.payment_link_description(registration.reference_id),
            name=registration.full_name,
            email=registration.email,
            contact=f"+91{registration.whatsapp}",
            reference_id=registration.reference_id,
            callback_url=callback_url,
            notes={
                "registration_id": str(registration.pk),
                "workshop": page.slug,
                "event": page.title,
                "reference": registration.reference_id,
            },
        )
    except RazorpayError:
        logger.exception("Failed to create Razorpay payment link")
        registration.delete()
        form.add_error(
            None,
            "We could not create your payment link. Please try again in a moment.",
        )
        return {"form": form}

    registration.payment_link = link.url
    registration.payment_link_id = link.id
    registration.save(update_fields=["payment_link", "payment_link_id"])
    return redirect(link.url)


@require_GET
def payment_callback(request: HttpRequest) -> HttpResponse:
    payment_link_id = request.GET.get("razorpay_payment_link_id", "")
    reference_id = request.GET.get("razorpay_payment_link_reference_id", "")
    status = request.GET.get("razorpay_payment_link_status", "")
    payment_id = request.GET.get("razorpay_payment_id", "")
    signature = request.GET.get("razorpay_signature", "")

    if not reference_id:
        return HttpResponseBadRequest("Missing payment reference.")

    registration = get_object_or_404(Registration, reference_id=reference_id)
    valid = verify_callback_signature(
        payment_link_id=payment_link_id,
        payment_link_reference_id=reference_id,
        payment_link_status=status,
        payment_id=payment_id,
        signature=signature,
    )
    if valid and status == "paid":
        _mark_paid(registration, payment_id)
        registration.refresh_from_db()

    return render(
        request,
        "workshop/payment_status.html",
        {
            "registration": registration,
            "workshop": registration.workshop,
            "verified": valid,
        },
    )


@require_GET
def payment_status(request: HttpRequest, reference_id: str) -> HttpResponse:
    registration = get_object_or_404(Registration, reference_id=reference_id)
    return render(
        request,
        "workshop/payment_status.html",
        {
            "registration": registration,
            "workshop": registration.workshop,
            "verified": True,
        },
    )


@require_http_methods(["GET", "POST"])
def mock_pay(request: HttpRequest, reference_id: str) -> HttpResponse:
    if not settings.RAZORPAY_MOCK:
        raise Http404()
    registration = get_object_or_404(Registration, reference_id=reference_id)
    if request.method == "POST":
        _mark_paid(registration, f"pay_mock_{reference_id}")
        return redirect("payment_status", reference_id=reference_id)
    return render(
        request,
        "workshop/mock_pay.html",
        {"registration": registration, "workshop": registration.workshop},
    )


@csrf_exempt
@require_POST
def razorpay_webhook(request: HttpRequest) -> HttpResponse:
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not settings.RAZORPAY_MOCK and not verify_webhook_signature(request.body, signature):
        return HttpResponse("invalid signature", status=400)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponse("invalid json", status=400)

    event = payload.get("event")
    if event != "payment_link.paid":
        return JsonResponse({"ignored": event or "unknown"})

    link_entity = (
        payload.get("payload", {}).get("payment_link", {}).get("entity", {})
    )
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    reference_id = link_entity.get("reference_id") or ""
    payment_link_id = link_entity.get("id") or ""
    payment_id = payment_entity.get("id") or ""

    registration = None
    if reference_id:
        registration = Registration.objects.filter(reference_id=reference_id).first()
    if registration is None and payment_link_id:
        registration = Registration.objects.filter(payment_link_id=payment_link_id).first()
    if registration is None:
        logger.warning("Webhook for unknown registration: %s / %s", reference_id, payment_link_id)
        return JsonResponse({"ok": True, "matched": False})

    _mark_paid(registration, payment_id, raw=payload)
    return JsonResponse({"ok": True, "reference_id": registration.reference_id})

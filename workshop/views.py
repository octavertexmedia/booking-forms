from __future__ import annotations

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.html import escape
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .forms import RegistrationForm
from .models import Registration, RegistrationStatus, WorkshopPackage, WorkshopPage
from .payments import PAID_EVENTS, confirm_paid, match_registration, payload_entity
from .razorpay_client import (
    RazorpayError,
    create_payment_link,
    has_api_keys,
    verify_callback_signature,
    verify_webhook_signature,
)
from .reminders import send_due_reminders

logger = logging.getLogger(__name__)


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True, "service": "cafe-orelo-workshop"})


@require_GET
def sitemap_xml(_request: HttpRequest) -> HttpResponse:
    from workshop.models import HomePage, WorkshopPage
    from workshop.seo import page_canonical

    urls: list[tuple[str, str, str]] = []
    home = HomePage.objects.live().public().first()
    if home:
        urls.append((page_canonical(home), "daily", "1.0"))
    for event in WorkshopPage.objects.live().public().order_by("workshop_date"):
        urls.append((page_canonical(event), "weekly", "0.9"))
    items = "".join(
        (
            "<url>"
            f"<loc>{escape(loc)}</loc>"
            f"<changefreq>{freq}</changefreq>"
            f"<priority>{priority}</priority>"
            "</url>"
        )
        for loc, freq, priority in urls
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}"
        "</urlset>"
    )
    return HttpResponse(body, content_type="application/xml; charset=utf-8")


@require_GET
def robots_txt(_request: HttpRequest) -> HttpResponse:
    base = (settings.PUBLIC_BASE_URL or "https://bookings.healthyome.in").rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /django-admin/\n"
        "Disallow: /payments/\n"
        "Disallow: /webhooks/\n"
        "Disallow: /cron/\n"
        "Disallow: /staff/\n"
        "Disallow: /documents/\n"
        "\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


# Older imports still expect these names.
_mark_paid = confirm_paid


def _payment_status_context(
    registration: Registration, *, verified: bool, reported_paid: bool = False
) -> dict:
    workshop = registration.workshop
    seats = int(registration.seats)
    uses_package = bool(registration.package_id or registration.package_name)
    return {
        "registration": registration,
        "workshop": workshop,
        "verified": verified,
        "uses_package_payment": uses_package,
        "uses_static_payment_link": (not uses_package) and workshop.uses_static_payment_link(),
        "price_per_seat": workshop.price_per_seat,
        "seat_pay_steps": list(range(1, seats + 1)),
        "reported_paid": reported_paid,
        "is_paid": registration.status == RegistrationStatus.PAID,
    }


def register(request: HttpRequest, page: WorkshopPage):
    form = RegistrationForm(page, request.POST or None)
    if request.method != "POST":
        return {"form": form}

    if not form.is_valid():
        return {"form": form}

    data = form.cleaned_data
    chosen: WorkshopPackage | None = data.get("package")
    if chosen is not None:
        seats = chosen.seats
        amount = chosen.price
    else:
        seats = data["seats"]
        amount = page.price_per_seat * seats

    registration = None
    for _attempt in range(3):
        try:
            with transaction.atomic():
                locked = WorkshopPage.objects.select_for_update().get(pk=page.pk)
                remaining = locked.seats_remaining()
                package = None
                package_name = ""
                payment_url = ""
                if chosen is not None:
                    package = locked.packages.filter(pk=chosen.pk).first()
                    if package is None or not package.has_payment_link():
                        form.add_error("package", "Choose an available package.")
                        return {"form": form}
                    seats = package.seats
                    amount = package.price
                    package_name = package.name
                    payment_url = package.payment_link.strip()
                if seats > remaining:
                    field = "package" if chosen is not None else "seats"
                    if remaining <= 0:
                        form.add_error(None, "This event is sold out.")
                    else:
                        form.add_error(
                            field,
                            f"Only {remaining} seat{'s' if remaining != 1 else ''} left for this event.",
                        )
                    return {"form": form}
                if chosen is None:
                    payment_url = (locked.payment_link_url or "").strip()
                registration = Registration.objects.create(
                    workshop=locked,
                    full_name=data["full_name"],
                    whatsapp=data["whatsapp"],
                    email=data["email"],
                    seats=seats,
                    amount=amount,
                    package=package,
                    package_name=package_name,
                    payment_link=payment_url,
                    reference_id=locked.next_reference_id(),
                    status=RegistrationStatus.PAYMENT_PENDING,
                )
            break
        except IntegrityError:
            registration = None
    if registration is None:
        form.add_error(None, "We could not hold that reservation. Please try again.")
        return {"form": form}

    if registration.payment_link:
        return redirect("payment_status", reference_id=registration.reference_id)

    if not settings.RAZORPAY_MOCK and not has_api_keys():
        logger.error("No Razorpay keys and no package/event payment link for %s", page.slug)
        registration.delete()
        form.add_error(
            None,
            "Payments are not configured for this event yet. Please contact Cafe Orelo.",
        )
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
        _payment_status_context(registration, verified=valid),
    )


@require_http_methods(["GET", "POST"])
def payment_status(request: HttpRequest, reference_id: str) -> HttpResponse:
    registration = get_object_or_404(Registration, reference_id=reference_id)
    reported_paid = False
    if request.method == "POST" and request.POST.get("reported_paid"):
        # Guests cannot flip status themselves — too easy to fake.
        reported_paid = registration.status != RegistrationStatus.PAID
    return render(
        request,
        "workshop/payment_status.html",
        _payment_status_context(
            registration, verified=True, reported_paid=reported_paid
        ),
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def admin_mark_paid(request: HttpRequest, pk: int) -> HttpResponse:
    registration = get_object_or_404(Registration, pk=pk)
    if request.method == "POST":
        _mark_paid(registration, registration.payment_id or "admin")
        messages.success(
            request,
            f"{registration.full_name} ({registration.reference_id}) is PAID. Invites sent if not already.",
        )
        next_url = request.POST.get("next") or request.GET.get("next") or "/admin/snippets/workshop/registration/"
        return redirect(next_url)
    return render(
        request,
        "workshop/admin_mark_paid.html",
        {"registration": registration, "workshop": registration.workshop},
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


def _webhook_health_payload() -> dict:
    secret_set = bool(settings.RAZORPAY_WEBHOOK_SECRET)
    if not secret_set:
        logger.error(
            "RAZORPAY_WEBHOOK_SECRET_TIRAMISU and RAZORPAY_WEBHOOK_SECRET are "
            "unset. Paste the bookings webhook signing secret from Razorpay "
            "Dashboard → Accounts & Settings → Webhooks."
        )
    return {
        "ok": True,
        "service": "razorpay-webhook",
        "secret_configured": secret_set,
        "whatsapp_api_url": settings.WHATSAPP_API_URL or "",
        "whatsapp_token_configured": bool(settings.WHATSAPP_API_TOKEN),
    }


@require_GET
def razorpay_webhook_health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse(_webhook_health_payload())


def _cron_secret_ok(request: HttpRequest) -> bool:
    expected = getattr(settings, "CRON_SECRET", "") or ""
    if not expected:
        logger.error("CRON_SECRET is not set; refusing reminder cron.")
        return False
    provided = (
        request.GET.get("secret")
        or request.POST.get("secret")
        or ""
    ).strip()
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        provided = provided or auth[7:].strip()
    return provided == expected


@csrf_exempt
@require_http_methods(["GET", "POST"])
def cron_reminders(request: HttpRequest) -> HttpResponse:
    if not _cron_secret_ok(request):
        return HttpResponse("unauthorized", status=401)
    force = request.GET.get("force") in {"1", "true", "yes"}
    result = send_due_reminders(force=force)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def razorpay_webhook(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return JsonResponse(_webhook_health_payload())

    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if settings.RAZORPAY_MOCK:
        logger.info("Razorpay webhook accepted under RAZORPAY_MOCK")
    elif secret:
        if not verify_webhook_signature(request.body, signature):
            logger.warning("Razorpay webhook rejected: invalid signature")
            return HttpResponse("invalid signature", status=400)
    else:
        logger.error(
            "RAZORPAY_WEBHOOK_SECRET_TIRAMISU and RAZORPAY_WEBHOOK_SECRET are "
            "unset. Processing webhook without signature verification. Paste "
            "the bookings webhook secret from Razorpay Dashboard → Webhooks."
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        logger.warning("Razorpay webhook invalid JSON")
        return HttpResponse("invalid json", status=400)

    event = payload.get("event") or ""
    if event not in PAID_EVENTS:
        logger.info("Razorpay webhook ignored event=%s", event or "unknown")
        return JsonResponse({"ok": True, "ignored": event or "unknown"})

    payment_entity = payload_entity(payload, "payment")
    order_entity = payload_entity(payload, "order")
    payment_id = str(payment_entity.get("id") or order_entity.get("id") or "")

    registration = match_registration(payload)
    if registration is None:
        logger.warning("Webhook %s did not match a registration", event)
        return JsonResponse({"ok": True, "matched": False, "event": event})

    confirm_paid(registration, payment_id, raw=payload)
    registration.refresh_from_db()
    logger.info(
        "Webhook %s confirmed %s paid=%s email=%s whatsapp=%s",
        event,
        registration.reference_id,
        registration.status,
        registration.email_invite_sent,
        registration.group_invite_sent,
    )
    return JsonResponse(
        {
            "ok": True,
            "matched": True,
            "reference_id": registration.reference_id,
            "event": event,
            "email_invite_sent": registration.email_invite_sent,
            "group_invite_sent": registration.group_invite_sent,
        }
    )

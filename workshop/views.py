from __future__ import annotations

import json
import logging
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.utils.html import escape
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .forms import RegistrationForm
from .models import Registration, RegistrationStatus, WorkshopPackage, WorkshopPage
from .payments import PAID_EVENTS, confirm_paid, match_from_callback, match_registration, payload_entity
from .razorpay_client import (
    RazorpayError,
    callback_secrets,
    create_payment_link,
    fetch_payment,
    fetch_payment_link,
    fetch_payment_link_by_reference,
    has_api_keys,
    payment_link_paid_info,
    verify_callback_signature,
    verify_webhook_signature,
)
from .reminders import send_due_reminders

logger = logging.getLogger(__name__)

SESSION_BOOKING_REF = "workshop_booking_reference"
PENDING_REF_COOKIE = "pending_registration_ref"
API_PAID_STATUSES = frozenset({"captured", "authorized"})


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "ok": True,
            "service": "cafe-orelo-workshop",
            "razorpay_keys_configured": has_api_keys(),
            "razorpay_webhook_secret_configured": bool(settings.RAZORPAY_WEBHOOK_SECRET),
        }
    )


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
    registration: Registration | None,
    *,
    verified: bool,
    cancelled: bool = False,
) -> dict:
    workshop = registration.workshop if registration else None
    seats = int(registration.seats) if registration else 0
    uses_package = bool(
        registration and (registration.package_id or registration.package_name)
    )
    is_paid = bool(registration and registration.status == RegistrationStatus.PAID)
    unique_link = bool(registration and registration.payment_link_id)
    return {
        "registration": registration,
        "workshop": workshop,
        "verified": verified,
        "uses_package_payment": uses_package,
        "uses_static_payment_link": bool(
            registration
            and workshop
            and (not unique_link)
            and (not uses_package)
            and workshop.uses_static_payment_link()
        ),
        "price_per_seat": workshop.price_per_seat if workshop else None,
        "seat_pay_steps": list(range(1, seats + 1)),
        "is_paid": is_paid,
        "cancelled": cancelled and not is_paid,
        "should_poll": bool(registration) and not is_paid,
    }


def _remember_booking(request: HttpRequest, registration: Registration) -> None:
    request.session[SESSION_BOOKING_REF] = registration.reference_id
    request.session.modified = True


def _attach_pending_cookie(response: HttpResponse, reference_id: str) -> HttpResponse:
    response.set_signed_cookie(
        PENDING_REF_COOKIE,
        reference_id,
        max_age=60 * 60 * 6,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
        path="/",
    )
    return response


def _pending_ref_from_request(request: HttpRequest) -> str:
    session_ref = str(request.session.get(SESSION_BOOKING_REF) or "").strip()
    try:
        cookie_ref = str(
            request.get_signed_cookie(PENDING_REF_COOKIE, default="") or ""
        ).strip()
    except Exception:
        cookie_ref = ""
    return session_ref or cookie_ref


def _redirect_to_pay(request: HttpRequest, registration: Registration, url: str):
    _remember_booking(request, registration)
    return _attach_pending_cookie(redirect(url), registration.reference_id)


def _callback_url_for(reference_id: str) -> str:
    base = (settings.PUBLIC_BASE_URL or "https://bookings.healthyome.in").rstrip("/")
    return f"{base}/payments/callback/?ref={quote(reference_id, safe='')}"


def _confirm_from_razorpay_link(registration: Registration) -> bool:
    """If Razorpay says this unique Payment Link is paid, mark PAID now."""
    if registration.status == RegistrationStatus.PAID:
        return True
    data = {}
    if registration.payment_link_id:
        data = fetch_payment_link(registration.payment_link_id)
    if not data:
        data = fetch_payment_link_by_reference(registration.reference_id)
    paid, payment_id = payment_link_paid_info(data)
    if not paid:
        return False
    link_id = str(data.get("id") or "").strip()
    if link_id and not registration.payment_link_id:
        registration.payment_link_id = link_id
        registration.save(update_fields=["payment_link_id"])
    confirm_paid(registration, payment_id or registration.payment_id)
    registration.refresh_from_db()
    return registration.status == RegistrationStatus.PAID


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
                fallback_url = ""
                if chosen is not None:
                    package = locked.packages.filter(pk=chosen.pk).first()
                    api_ok = locked._api_checkout_available()
                    if package is None or (not api_ok and not package.has_payment_link()):
                        form.add_error("package", "Choose an available package.")
                        return {"form": form}
                    seats = package.seats
                    amount = package.price
                    package_name = package.name
                    fallback_url = (package.payment_link or "").strip()
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
                    fallback_url = (locked.payment_link_url or "").strip()
                registration = Registration.objects.create(
                    workshop=locked,
                    full_name=data["full_name"],
                    whatsapp=data["whatsapp"],
                    email=data["email"],
                    seats=seats,
                    amount=amount,
                    package=package,
                    package_name=package_name,
                    payment_link="",
                    reference_id=locked.next_reference_id(),
                    status=RegistrationStatus.PAYMENT_PENDING,
                )
                registration._fallback_url = fallback_url
            break
        except IntegrityError:
            registration = None
    if registration is None:
        form.add_error(None, "We could not hold that reservation. Please try again.")
        return {"form": form}

    fallback_url = getattr(registration, "_fallback_url", "") or ""
    if has_api_keys() or settings.RAZORPAY_MOCK:
        try:
            link = create_payment_link(
                amount_paise=registration.amount_paise,
                description=page.payment_link_description(registration.reference_id),
                name=registration.full_name,
                email=registration.email,
                contact=f"+91{registration.whatsapp}",
                reference_id=registration.reference_id,
                callback_url=_callback_url_for(registration.reference_id),
                notes={
                    "reference": registration.reference_id,
                    "email": registration.email,
                    "whatsapp": registration.whatsapp,
                    "package": registration.package_name or "",
                    "registration_id": str(registration.pk),
                    "workshop": page.slug,
                },
            )
        except RazorpayError:
            logger.exception(
                "Failed to create Razorpay payment link for %s",
                registration.reference_id,
            )
            registration.delete()
            form.add_error(
                None,
                "We could not create your payment link. Please try again in a moment.",
            )
            return {"form": form}
        registration.payment_link = link.url
        registration.payment_link_id = link.id
        registration.save(update_fields=["payment_link", "payment_link_id"])
        return _redirect_to_pay(request, registration, link.url)

    if fallback_url:
        logger.error(
            "Razorpay API keys missing — falling back to static link for %s",
            registration.reference_id,
        )
        registration.payment_link = fallback_url
        registration.save(update_fields=["payment_link"])
        return _redirect_to_pay(request, registration, fallback_url)

    logger.error(
        "No Razorpay keys and no static payment link for %s — unique Payment Links require RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET",
        page.slug,
    )
    registration.delete()
    form.add_error(
        None,
        "Payments are not configured for this event yet. Please try again shortly.",
    )
    return {"form": form}


def _callback_param(request: HttpRequest, *names: str) -> str:
    for name in names:
        value = request.POST.get(name) or request.GET.get(name) or ""
        if value:
            return str(value).strip()
    return ""


def _callback_json(request: HttpRequest) -> dict:
    content_type = request.content_type or ""
    if "json" not in content_type:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


@csrf_exempt
@require_http_methods(["GET", "POST"])
def payment_callback(request: HttpRequest) -> HttpResponse:
    body = _callback_json(request)
    payment_link_id = _callback_param(request, "razorpay_payment_link_id") or str(
        body.get("razorpay_payment_link_id") or ""
    ).strip()
    reference_id = _callback_param(
        request, "ref", "razorpay_payment_link_reference_id", "reference_id"
    ) or str(
        body.get("ref")
        or body.get("razorpay_payment_link_reference_id")
        or body.get("reference_id")
        or ""
    ).strip()
    status = (
        _callback_param(request, "razorpay_payment_link_status", "status")
        or str(body.get("razorpay_payment_link_status") or body.get("status") or "")
    ).strip().lower()
    payment_id = _callback_param(request, "razorpay_payment_id", "payment_id") or str(
        body.get("razorpay_payment_id") or body.get("payment_id") or ""
    ).strip()
    signature = _callback_param(request, "razorpay_signature") or str(
        body.get("razorpay_signature") or ""
    ).strip()
    email = (
        _callback_param(request, "email", "razorpay_email", "customer_email")
        or str(body.get("email") or body.get("razorpay_email") or "")
    ).strip().lower()
    contact = _callback_param(
        request, "contact", "phone", "whatsapp", "razorpay_contact"
    ) or str(body.get("contact") or body.get("phone") or "")

    payment = fetch_payment(payment_id)
    notes = payment.get("notes") if isinstance(payment.get("notes"), dict) else {}
    if not email:
        email = str(payment.get("email") or "").strip().lower()
    if not contact:
        contact = str(payment.get("contact") or "")
    api_paid = str(payment.get("status") or "").lower() in API_PAID_STATUSES

    signature_ok = verify_callback_signature(
        payment_link_id=payment_link_id,
        payment_link_reference_id=reference_id,
        payment_link_status=status,
        payment_id=payment_id,
        signature=signature,
    )
    secret_configured = bool(callback_secrets()) and not settings.RAZORPAY_MOCK
    callback_paid = status == "paid"
    paid_evidence = api_paid or (
        callback_paid and (signature_ok or not secret_configured)
    )
    if secret_configured and signature and not signature_ok and not api_paid:
        paid_evidence = False

    registration = match_from_callback(
        reference_id=reference_id,
        payment_link_id=payment_link_id,
        payment_id=payment_id,
        email=email,
        contact=contact,
        notes=notes,
    )
    pending_ref = _pending_ref_from_request(request)
    if registration is None and pending_ref:
        registration = Registration.objects.filter(reference_id=pending_ref).first()
        if registration:
            logger.info("Callback matched %s from session/cookie", registration.reference_id)

    if registration is None:
        logger.warning(
            "Payment callback did not match a registration reference=%s plink=%s payment=%s",
            reference_id or "—",
            payment_link_id or "—",
            payment_id or "—",
        )
        event = WorkshopPage.objects.live().public().first()
        if event:
            return redirect(event.url)
        return redirect("/")

    _remember_booking(request, registration)
    if payment_link_id and not registration.payment_link_id:
        registration.payment_link_id = payment_link_id
        registration.save(update_fields=["payment_link_id"])

    session_matches = pending_ref == registration.reference_id
    if not paid_evidence and (not signature or session_matches):
        paid_evidence = _confirm_from_razorpay_link(registration)
        if paid_evidence:
            registration.refresh_from_db()

    if paid_evidence and registration.status != RegistrationStatus.PAID:
        _mark_paid(registration, payment_id)
        registration.refresh_from_db()

    if registration.status == RegistrationStatus.PAID:
        response = redirect("payment_status", reference_id=registration.reference_id)
    else:
        response = redirect(
            f"/payments/status/{registration.reference_id}/?cancelled=1"
        )
    return _attach_pending_cookie(response, registration.reference_id)


@require_GET
def payment_status_poll(request: HttpRequest, reference_id: str) -> JsonResponse:
    registration = get_object_or_404(Registration, reference_id=reference_id)
    if registration.status != RegistrationStatus.PAID:
        _confirm_from_razorpay_link(registration)
        registration.refresh_from_db()
    paid = registration.status == RegistrationStatus.PAID
    return JsonResponse(
        {
            "ok": True,
            "reference_id": registration.reference_id,
            "status": registration.status,
            "paid": paid,
            "reload": paid,
        }
    )


@require_http_methods(["GET", "POST"])
def payment_status(request: HttpRequest, reference_id: str) -> HttpResponse:
    registration = get_object_or_404(Registration, reference_id=reference_id)
    if registration.status != RegistrationStatus.PAID:
        _confirm_from_razorpay_link(registration)
        registration.refresh_from_db()
    cancelled = request.GET.get("cancelled") in {"1", "true", "yes"}
    _remember_booking(request, registration)
    response = render(
        request,
        "workshop/payment_status.html",
        _payment_status_context(
            registration,
            verified=True,
            cancelled=cancelled,
        ),
    )
    return _attach_pending_cookie(response, registration.reference_id)


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
        "razorpay_keys_configured": has_api_keys(),
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

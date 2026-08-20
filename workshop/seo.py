"""Public SEO / AEO / GEO helpers for HealthyOme Bookings + Cafe Orelo events."""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.templatetags.static import static

SITE_NAME = "HealthyOme Bookings"
OG_LOCALE = "en_IN"
IN_LANGUAGE = "en-IN"
TIMEZONE = ZoneInfo("Asia/Kolkata")
OG_CACHE = "20260820-og"
OG_HOME = "workshop/images/og-home.png"
OG_TIRAMISU = "workshop/images/og-tiramisu.png"
FAVICON = "workshop/images/cafe-orelo-favicon.png"
APPLE_TOUCH = "workshop/images/apple-touch-icon.png"


def public_base_url() -> str:
    return (getattr(settings, "PUBLIC_BASE_URL", "") or "https://bookings.healthyome.in").rstrip("/")


def absolute_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{public_base_url()}{path}"


def absolute_static(path: str, *, cache: str | None = OG_CACHE) -> str:
    url = static(path)
    if not (url.startswith("http://") or url.startswith("https://")):
        url = absolute_url(url)
    if cache:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}v={cache}"
    return url


def page_canonical(page) -> str:
    url_path = page.url or "/"
    return absolute_url(url_path)


def workshop_iso_start(workshop) -> str:
    return datetime.combine(workshop.workshop_date, workshop.start_time, tzinfo=TIMEZONE).isoformat()


def workshop_iso_end(workshop) -> str:
    return datetime.combine(workshop.workshop_date, workshop.end_time, tzinfo=TIMEZONE).isoformat()


def compact_date(workshop) -> str:
    return workshop.workshop_date.strftime("%-d %b %Y")


def compact_time(workshop) -> str:
    start = workshop.start_time.strftime("%-I").lstrip("0") or "0"
    end = workshop.end_time.strftime("%-I %p").lstrip("0")
    return f"{start}–{end}"


def price_label(workshop) -> str:
    return f"₹{workshop.price_per_seat.quantize(Decimal('1'))}"


def default_title(workshop, *, for_home: bool = False) -> str:
    name = (workshop.workshop_subtitle or workshop.title or "Workshop").strip()
    if for_home:
        return f"Cafe Orelo {workshop.hero_title} Workshop | {SITE_NAME}"[:60]
    title = f"{name} | Cafe Orelo"
    if len(title) <= 60:
        return title
    return f"{workshop.hero_title} Workshop | Cafe Orelo"[:60]


def _sentence(text: str) -> str:
    text = " ".join(text.split()).strip()
    if text and not text.endswith("."):
        text += "."
    return text


def _fit_description(core: str, extras: list[str]) -> str:
    """Keep the longest whole-phrase description that fits 150–160 characters."""
    text = _sentence(core)
    chosen = text
    for extra in extras:
        extra = _sentence(extra)
        if not extra:
            continue
        nxt = f"{text} {extra}"
        if len(nxt) <= 160:
            text = nxt
            chosen = nxt
            if 150 <= len(nxt) <= 160:
                return nxt
    if 150 <= len(chosen) <= 160:
        return chosen
    if len(chosen) < 150:
        for closer in ("Limited seats.", "Book now.", "Book at bookings.healthyome.in."):
            nxt = f"{_sentence(chosen)} {closer}"
            if len(nxt) <= 160:
                chosen = nxt
                if 150 <= len(nxt) <= 160:
                    return nxt
    return chosen


def default_description(workshop, *, for_home: bool = False) -> str:
    """Build a 150–160 character description from live event fields."""
    name = (workshop.workshop_subtitle or "Tiramisu Making Workshop").strip()
    chef = workshop.chef_display_name()
    venue = (workshop.venue or "Cafe Orelo").strip()
    date = compact_date(workshop)
    time = compact_time(workshop)
    price = price_label(workshop)
    wa = workshop.enquiry_whatsapp_display()
    if for_home:
        core = (
            f"Book Cafe Orelo's {name} with Chef {chef}. "
            f"{date}, {time}. {price} per seat."
        )
    else:
        core = f"{name} at {venue} with Chef {chef}. {date}, {time}. {price} per seat."
    extras = []
    if wa:
        extras.append(f"Enquire on WhatsApp {wa}.")
    extras.extend(["Limited seats.", "Book at bookings.healthyome.in."])
    return _fit_description(core, extras)


def og_image_for_workshop(workshop) -> str:
    if getattr(workshop, "slug", "") == "tiramisu-workshop":
        return absolute_static(OG_TIRAMISU)
    return absolute_static(OG_HOME)


def offer_availability(workshop) -> str:
    try:
        if getattr(workshop, "pk", None) and workshop.is_sold_out():
            return "https://schema.org/SoldOut"
    except Exception:
        pass
    return "https://schema.org/LimitedAvailability"


def event_json_ld(workshop, *, canonical: str | None = None) -> dict:
    url = canonical or page_canonical(workshop)
    image = og_image_for_workshop(workshop)
    chef = workshop.chef_display_name()
    venue = (workshop.venue or "Cafe Orelo").strip()
    return {
        "@type": "Event",
        "@id": f"{url.rstrip('/')}/#event",
        "name": workshop.workshop_subtitle or workshop.title,
        "description": default_description(workshop),
        "url": url,
        "inLanguage": IN_LANGUAGE,
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "eventStatus": "https://schema.org/EventScheduled",
        "startDate": workshop_iso_start(workshop),
        "endDate": workshop_iso_end(workshop),
        "image": [image, absolute_static("workshop/images/chef-aanchal-tiramisu.png")],
        "location": {
            "@type": "Place",
            "name": venue,
        },
        "organizer": {
            "@type": "Organization",
            "name": "Cafe Orelo",
            "url": public_base_url() + "/",
        },
        "performer": {
            "@type": "Person",
            "name": chef,
            "jobTitle": "Pastry Chef",
        },
        "offers": {
            "@type": "Offer",
            "url": url,
            "price": f"{workshop.price_per_seat.quantize(Decimal('1'))}",
            "priceCurrency": "INR",
            "availability": offer_availability(workshop),
        },
        "speakable": {
            "@type": "SpeakableSpecification",
            "cssSelector": [".flyer-title", ".fact-row", ".price-bar", ".gold-banner"],
        },
    }


def website_json_ld() -> list[dict]:
    base = public_base_url()
    org_id = f"{base}/#organization"
    site_id = f"{base}/#website"
    return [
        {
            "@type": "Organization",
            "@id": org_id,
            "name": SITE_NAME,
            "url": f"{base}/",
            "inLanguage": IN_LANGUAGE,
            "areaServed": {"@type": "Country", "name": "India"},
            "logo": absolute_static("workshop/images/cafe-orelo-logo.png"),
        },
        {
            "@type": "WebSite",
            "@id": site_id,
            "name": SITE_NAME,
            "url": f"{base}/",
            "inLanguage": IN_LANGUAGE,
            "publisher": {"@id": org_id},
        },
    ]


def graph_payload(*nodes) -> dict:
    items = []
    for node in nodes:
        if node is None:
            continue
        if isinstance(node, list):
            items.extend(node)
        else:
            items.append(node)
    return {"@context": "https://schema.org", "@graph": items}


def json_ld_script(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

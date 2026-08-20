from datetime import date, time
from decimal import Decimal
from zoneinfo import ZoneInfo
import re

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join, mark_safe
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, HelpPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.images import get_image_model_string
from wagtail.models import Orderable, Page

IST = ZoneInfo("Asia/Kolkata")

def format_ist(dt) -> str:
    """Admin / CSV timestamp in India Standard Time, e.g. 21 Aug 2026, 01:59 AM IST."""
    if not dt:
        return "—"
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, IST)
    return timezone.localtime(dt, IST).strftime("%d %b %Y, %I:%M %p IST")


TAKE_HOME_ICONS = ("cake", "book", "hat", "cup", "heart")
TAKE_HOME_ORBS = ("pink", "blue", "orange", "green", "purple")
DEFAULT_ENQUIRY_WHATSAPP = "7709818290"

DEFAULT_CONFIRMATION = (
    "🎉 Registration Confirmed!\n\n"
    "Hi {{name}} 👋\n\n"
    "Your registration for {{event}} at {{venue}} is confirmed! 🍰\n\n"
    "📅 {{date}}\n"
    "⏰ {{time}}\n"
    "📍 {{venue}}\n"
    "👩‍🍳 {{chef}}\n\n"
    "💳 Payment: ₹{{amount}} — PAID\n\n"
    "👥 Join the workshop WhatsApp group:\n"
    "{{group_invite_link}}\n\n"
    "We’ll share all workshop updates and important details in the group.\n\n"
    "See you at {{venue}}! 🤎"
)

DEFAULT_REMINDER = (
    "🍰 {{event}} is tomorrow!\n\n"
    "We're excited to see you at {{venue}} tomorrow from {{time}}.\n\n"
    "Please arrive 10 minutes early.\n\n"
    "See you tomorrow! 🤎"
)

DEFAULT_EMAIL_SUBJECT = "You’re confirmed for {{event}} at Cafe Orelo"

DEFAULT_EMAIL_BODY = (
    "Hi {{name}},\n\n"
    "Your payment is confirmed for {{event}}.\n\n"
    "📅 {{date}}\n"
    "⏰ {{time}}\n"
    "📍 {{venue}}\n"
    "👩‍🍳 {{chef}}\n"
    "🎟️ Package: {{package}}\n\n"
    "Join the WhatsApp group for this workshop (the same invite we send on WhatsApp):\n"
    "{{group_invite_link}}\n\n"
    "Reference: {{reference}}\n"
    "Seats: {{seats}}\n"
    "Amount paid: ₹{{amount}}\n\n"
    "See you at {{venue}}!\n"
    "Cafe Orelo\n"
)

DEFAULT_REMINDER_EMAIL_SUBJECT = "Reminder: {{event}} at Cafe Orelo"

DEFAULT_TAKE_HOME = (
    "Your own handmade eggless tiramisu\n"
    "Detailed recipe sheet\n"
    "Hands-on learning & techniques\n"
    "Complimentary beverage\n"
    "A fun baking experience with fellow dessert lovers"
)

PACKAGE_HELP = (
    "Use Add package under the last row. Fill name, seats, and price (₹). "
    "Move up / Move down reorders the list. Delete this package removes that row. "
    "Guests only see published packages. The Razorpay URL is optional — "
    "checkout creates a unique Payment Link."
)

HOME_HELP = (
    "<p><strong>This page is the public homepage</strong> "
    "(<code>https://bookings.healthyome.in/</code>).</p>"
    "<p>Every line guests see on that URL is edited here: header tagline, "
    "logo, flyer title, gold banner, date / time / venue, take-homes, price, "
    "Book button, WhatsApp, chef photo, and footer. Change a field, then "
    "<strong>Publish</strong>.</p>"
    "<p>The green <strong>Book</strong> button still opens the first published "
    "Event (packages and the booking form live on that Event). Publishing "
    "Home also copies flyer date, time, venue, price, and copy onto that "
    "Event when it is the only one live, so the booking page stays in sync.</p>"
    "<p>When two or more Events are live, guests see cards instead of the "
    "single flyer. Use the listing headings at the bottom for that view.</p>"
)

EVENT_HELP = (
    "<p><strong>How this event works</strong></p>"
    "<p>Publish this page → share the URL → guests pay → they immediately see "
    "<strong>Join the WhatsApp group</strong> (the invite you paste below). "
    "Paid guests also get WhatsApp + email with the same invite.</p>"
    "<p>Payment: use <strong>Add package</strong> below (name, seats, price). "
    "Delete a row with <strong>Delete this package</strong>. Reorder with <strong>Move up</strong> / <strong>Move down</strong>. "
    "On submit we always create a <strong>unique Razorpay Payment Link</strong> "
    "for that booking (reference <code>TIRAMISU-…</code>). "
    "The package’s static rzp.io URL is unused for checkout when API keys are set.</p>"
    "<p>After pay, Razorpay returns to "
    "<code>https://bookings.healthyome.in/payments/callback/?ref=&lt;REFERENCE&gt;</code>. "
    "That request marks the row PAID. The webhook is backup.</p>"
    "<p><strong>Set Razorpay webhook to "
    "<code>https://bookings.healthyome.in/webhooks/razorpay/</code> "
    "for <code>payment.captured</code> and <code>payment_link.paid</code></strong> "
    "(also subscribe to <code>payment.authorized</code> and <code>order.paid</code>). "
    "Paste the webhook signing secret into Vercel as "
    "<code>RAZORPAY_WEBHOOK_SECRET_TIRAMISU</code> "
    "(or <code>RAZORPAY_WEBHOOK_SECRET</code>).</p>"
    "<p>To run another date or dish: in <strong>Pages</strong>, open Cafe Orelo and "
    "<strong>Add Event</strong>, or copy this page and change the date, packages, and invite links. "
    "The public booking URL is this page’s slug (for example <code>/tiramisu-workshop/</code>).</p>"
    "<p>The public homepage flyer is edited on <strong>Home</strong> "
    "(<a href=\"/admin/pages/3/edit/\">Cafe Orelo</a>), not here. This Event "
    "owns the booking form, packages, WhatsApp group invite, and emails. "
    "Publishing Home copies flyer date / time / price onto this Event when "
    "it is the only live Event.</p>"
)

HOME_EVENT_SYNC_FIELDS = (
    "tagline",
    "hero_title",
    "hero_kicker",
    "gold_banner",
    "take_home_intro",
    "take_home_list",
    "limited_seats_line",
    "price_bar_label",
    "cta_label",
    "enquiry_whatsapp",
    "chef_name",
    "workshop_date",
    "start_time",
    "end_time",
    "venue",
    "price_per_seat",
)


class FlyerDisplayMixin:
    """Date / take-home / WhatsApp helpers shared by Home and Event flyers."""

    date_label = "Date"
    time_label = "Time"
    location_label = "Location"
    sold_out_line = "Sold out"
    chef_byline = "By"
    chef_role = "Pastry Chef"

    def take_home_items(self) -> list[str]:
        return [line.strip() for line in (self.take_home_list or "").splitlines() if line.strip()]

    def take_home_display(self) -> list[dict[str, str]]:
        items = []
        for index, text in enumerate(self.take_home_items()):
            items.append(
                {
                    "text": text,
                    "icon": TAKE_HOME_ICONS[index % len(TAKE_HOME_ICONS)],
                    "orb": TAKE_HOME_ORBS[index % len(TAKE_HOME_ORBS)],
                }
            )
        return items

    def enquiry_whatsapp_digits(self) -> str:
        digits = re.sub(r"\D", "", self.enquiry_whatsapp or "")
        if len(digits) >= 10:
            return digits[-10:]
        return ""

    def enquiry_whatsapp_url(self) -> str:
        digits = self.enquiry_whatsapp_digits()
        return f"https://wa.me/91{digits}" if digits else ""

    def enquiry_whatsapp_display(self) -> str:
        return self.enquiry_whatsapp_digits()

    def format_date(self) -> str:
        return self.workshop_date.strftime("%-d %B %Y")

    def format_time_range(self) -> str:
        start = self.start_time.strftime("%-I:%M %p")
        end = self.end_time.strftime("%-I:%M %p")
        return f"{start} – {end}"

    def format_flyer_date(self) -> str:
        """All-caps flyer line, e.g. SUNDAY 23RD AUGUST 2026."""
        day = self.workshop_date.day
        if 11 <= day <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        weekday = self.workshop_date.strftime("%A").upper()
        month = self.workshop_date.strftime("%B").upper()
        return f"{weekday} {day}{suffix.upper()} {month} {self.workshop_date.year}"

    def format_flyer_time(self) -> str:
        """Zero-padded flyer line, e.g. 03:00 PM TO 05:00 PM."""
        start = self.start_time.strftime("%I:%M %p")
        end = self.end_time.strftime("%I:%M %p")
        return f"{start} TO {end}"

    def chef_display_name(self) -> str:
        name = (self.chef_name or "").strip()
        if name.lower().startswith("chef "):
            return name[5:].strip()
        return name or "Aanchal Wadhwa"


class FlyerFacade:
    """Lets the shared flyer template read Home copy plus Event sold-out state."""

    def __init__(self, home, event=None):
        self._home = home
        self._event = event

    def __getattr__(self, name):
        return getattr(self._home, name)

    def is_sold_out(self) -> bool:
        return bool(self._event and self._event.is_sold_out())


class HomeGuidePanel(HelpPanel):
    """Tells kitchen staff which page owns the flyer they see on /."""

    class BoundPanel(HelpPanel.BoundPanel):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.content = mark_safe(HOME_HELP + self._event_links())

        def _event_links(self) -> str:
            page = self.instance
            if not page or not page.pk:
                return (
                    "<p>Save this page, then add an Event under it to control "
                    "the flyer.</p>"
                )
            events = list(
                WorkshopPage.objects.descendant_of(page).order_by("workshop_date")
            )
            if not events:
                return (
                    "<p>No Event pages yet. Open Pages → this Home → "
                    "<strong>Add Event</strong>.</p>"
                )
            live = [event for event in events if event.live]
            featured_id = live[0].pk if len(live) == 1 else None
            rows = []
            for event in events:
                note = ""
                if featured_id and event.pk == featured_id:
                    note = " — Book button on / opens this Event"
                state = "published" if event.live else "draft"
                rows.append(
                    (
                        reverse("wagtailadmin_pages:edit", args=[event.pk]),
                        event.get_admin_display_title(),
                        f"{state}{note}",
                    )
                )
            return str(
                format_html(
                    "<p><strong>Events under this Home</strong></p><ul>{}</ul>",
                    format_html_join(
                        "",
                        '<li><a href="{}">{}</a> ({})</li>',
                        rows,
                    ),
                )
            )


class HomePage(FlyerDisplayMixin, Page):
    """Cafe landing page. Owns every line guests see on /."""

    brand_tagline = models.CharField(
        max_length=80,
        default="good food, good mood.",
        verbose_name="Header tagline",
        help_text="Under the Cafe Orelo logo on every public page.",
    )
    logo = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Header logo",
        help_text="Optional. Leave blank to keep the Cafe Orelo wordmark.",
    )
    footer_line = models.CharField(
        max_length=160,
        default="Cafe Orelo · seats confirmed only after payment",
        verbose_name="Footer line",
        help_text="Top line of the public footer (above the Octavertex credit).",
    )
    tagline = models.CharField(
        max_length=80,
        default="Learn. Create. Indulge.",
        verbose_name="Script line at the top",
    )
    hero_title = models.CharField(
        max_length=40,
        default="Tiramisu",
        verbose_name="Big title on the flyer",
    )
    hero_kicker = models.CharField(
        max_length=80,
        default="Making Workshop",
        verbose_name="Small title under the big word",
    )
    gold_banner = models.CharField(
        max_length=80,
        default="Eggless tiramisu making",
        verbose_name="Gold banner line",
    )
    workshop_date = models.DateField(
        default=date(2026, 8, 23),
        verbose_name="Date on the flyer",
    )
    start_time = models.TimeField(
        default=time(15, 0),
        verbose_name="Start time",
    )
    end_time = models.TimeField(
        default=time(17, 0),
        verbose_name="End time",
    )
    venue = models.CharField(
        max_length=120,
        default="Cafe Orelo",
        verbose_name="Location",
    )
    date_label = models.CharField(
        max_length=24,
        default="Date",
        verbose_name="Date label",
    )
    time_label = models.CharField(
        max_length=24,
        default="Time",
        verbose_name="Time label",
    )
    location_label = models.CharField(
        max_length=24,
        default="Location",
        verbose_name="Location label",
    )
    take_home_intro = models.CharField(
        max_length=80,
        default="What you will take home?",
        verbose_name="Take-home heading",
    )
    take_home_list = models.TextField(
        default=DEFAULT_TAKE_HOME,
        verbose_name="What guests take home",
        help_text="One item per line. These show on the public homepage flyer.",
    )
    price_bar_label = models.CharField(
        max_length=80,
        default="Registration charges",
        verbose_name="Price bar label",
    )
    price_per_seat = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1499.00"),
        verbose_name="Price on the flyer (₹)",
        help_text="Magenta bar on the homepage. Publishing Home copies this onto the live Event.",
    )
    limited_seats_line = models.CharField(
        max_length=120,
        default="Limited seats. Book your spot now!",
        verbose_name="Limited seats line",
    )
    sold_out_line = models.CharField(
        max_length=80,
        default="Sold out",
        verbose_name="Sold-out line",
        help_text="Replaces the limited-seats line when the Event has no seats left.",
    )
    cta_label = models.CharField(
        max_length=40,
        default="Book your spot now",
        verbose_name="Book button label",
    )
    enquiry_whatsapp = models.CharField(
        max_length=16,
        default=DEFAULT_ENQUIRY_WHATSAPP,
        blank=True,
        verbose_name="Enquiry WhatsApp number",
        help_text="10-digit Indian number on the flyer. Leave blank to hide the link.",
    )
    chef_name = models.CharField(
        max_length=120,
        default="Aanchal Wadhwa",
        verbose_name="Chef name",
    )
    chef_byline = models.CharField(
        max_length=24,
        default="By",
        verbose_name="Chef chip — small word",
    )
    chef_role = models.CharField(
        max_length=40,
        default="Pastry Chef",
        verbose_name="Chef chip — role",
    )
    intro = RichTextField(
        blank=True,
        verbose_name="Welcome line",
        help_text="Optional extra copy above the flyer or the card list. Leave blank to hide it.",
    )
    hero_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Home hero image",
        help_text=(
            "Photo on the right of the homepage flyer. Leave blank to use the Event "
            "photo, or the default chef crop."
        ),
    )
    listing_tagline = models.CharField(
        max_length=80,
        default="Learn. Create. Indulge.",
        verbose_name="Listing tagline",
        help_text="Script line when several events are listed, or none are live.",
    )
    listing_title = models.CharField(
        max_length=40,
        default="Bookings",
        verbose_name="Listing title",
        help_text="Big word on the multi-event homepage. Unused when the single flyer is showing.",
    )
    listing_kicker = models.CharField(
        max_length=80,
        default="Cafe Orelo workshops",
        verbose_name="Listing kicker",
        help_text="Small line under the listing title.",
    )
    empty_lede = models.CharField(
        max_length=180,
        default="No workshop is published yet. Check back shortly.",
        verbose_name="Empty-state line",
        help_text="Shown when no Event is published.",
    )
    card_cta_label = models.CharField(
        max_length=40,
        default="Book your spot",
        verbose_name="Card button label",
        help_text="Button on each event card when several events are live.",
    )

    content_panels = Page.content_panels + [
        HomeGuidePanel(heading="What this page controls"),
        MultiFieldPanel(
            [
                FieldPanel("logo"),
                FieldPanel("brand_tagline"),
                FieldPanel("footer_line"),
            ],
            heading="Header & footer (every public page)",
        ),
        MultiFieldPanel(
            [
                FieldPanel("tagline"),
                FieldPanel("hero_title"),
                FieldPanel("hero_kicker"),
                FieldPanel("gold_banner"),
                FieldPanel("date_label"),
                FieldPanel("workshop_date"),
                FieldPanel("time_label"),
                FieldPanel("start_time"),
                FieldPanel("end_time"),
                FieldPanel("location_label"),
                FieldPanel("venue"),
                FieldPanel("take_home_intro"),
                FieldPanel("take_home_list"),
                FieldPanel("price_bar_label"),
                FieldPanel("price_per_seat"),
                FieldPanel("limited_seats_line"),
                FieldPanel("sold_out_line"),
                FieldPanel("cta_label"),
                FieldPanel("enquiry_whatsapp"),
                FieldPanel("intro"),
            ],
            heading="Homepage flyer (what guests see on /)",
        ),
        MultiFieldPanel(
            [
                FieldPanel("hero_image"),
                FieldPanel("chef_name"),
                FieldPanel("chef_byline"),
                FieldPanel("chef_role"),
            ],
            heading="Chef photo",
        ),
        MultiFieldPanel(
            [
                FieldPanel("listing_tagline"),
                FieldPanel("listing_title"),
                FieldPanel("listing_kicker"),
                FieldPanel("empty_lede"),
                FieldPanel("card_cta_label"),
            ],
            heading="Listing headings (several events, or none)",
        ),
    ]

    max_count = 1

    def get_context(self, request, *args, **kwargs):
        from workshop import seo

        context = super().get_context(request, *args, **kwargs)
        events = list(
            WorkshopPage.objects.live().public().descendant_of(self).order_by("workshop_date")
        )
        workshop = events[0] if events else None
        context["events"] = events
        context["workshop"] = workshop
        context["flyer"] = FlyerFacade(self, workshop)
        context["show_event_cards"] = len(events) > 1
        context["home_hero"] = self.hero_image or (workshop.hero_image if workshop else None)
        context["canonical_url"] = seo.page_canonical(self)
        context["og_type"] = "website"
        context["og_image_url"] = seo.absolute_static(seo.OG_HOME)
        context["robots"] = "index, follow, max-image-preview:large"
        if workshop:
            context["seo_title"] = self.seo_title or seo.default_title(workshop, for_home=True)
            context["seo_description"] = self.search_description or seo.default_description(
                workshop, for_home=True
            )
            context["og_image_alt"] = (
                f"Cafe Orelo {workshop.workshop_subtitle} with Chef {workshop.chef_display_name()}, "
                f"{workshop.format_date()}, {workshop.format_time_range()}, {seo.price_label(workshop)}"
            )
            if len(events) == 1:
                context["event_json_ld"] = seo.json_ld_script(
                    seo.graph_payload(
                        seo.event_json_ld(workshop, canonical=seo.page_canonical(workshop))
                    )
                )
            else:
                context["event_json_ld"] = seo.json_ld_script(
                    {
                        "@context": "https://schema.org",
                        "@type": "ItemList",
                        "name": "Cafe Orelo workshops",
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": index,
                                "url": seo.page_canonical(event),
                                "name": event.workshop_subtitle,
                            }
                            for index, event in enumerate(events, start=1)
                        ],
                    }
                )
        else:
            context["seo_title"] = self.seo_title or f"Cafe Orelo Workshops | {seo.SITE_NAME}"
            context["seo_description"] = (
                self.search_description
                or "Cafe Orelo workshops on HealthyOme Bookings. New hands-on classes are listed here when they go live."
            )
            context["og_image_alt"] = context.get("seo_og_default_alt", "Cafe Orelo workshop bookings")
        return context

    def sync_featured_event(self) -> bool:
        """Copy flyer fields onto the only live Event so the booking page matches /."""
        events = list(
            WorkshopPage.objects.live().public().descendant_of(self).order_by("workshop_date")
        )
        if len(events) != 1:
            return False
        event = events[0]
        changed = False
        for field in HOME_EVENT_SYNC_FIELDS:
            value = getattr(self, field)
            if getattr(event, field) != value:
                setattr(event, field, value)
                changed = True
        if changed:
            event.save_revision().publish()
        return changed


class WorkshopPage(FlyerDisplayMixin, Page):
    """One reusable event: its own form, price, Razorpay links, and post-pay invites."""

    workshop_date = models.DateField(verbose_name="Event date")
    start_time = models.TimeField(verbose_name="Start time")
    end_time = models.TimeField(verbose_name="End time")
    venue = models.CharField(max_length=120, default="Cafe Orelo", verbose_name="Venue")
    chef_name = models.CharField(
        max_length=120,
        default="Aanchal Wadhwa",
        verbose_name="Chef name",
    )
    workshop_subtitle = models.CharField(
        max_length=160,
        default="Eggless Tiramisu Making Workshop",
        verbose_name="Event name (on the page and in messages)",
        help_text="Shown on the page and in WhatsApp / email. Use {{event}} in the templates below.",
    )
    tagline = models.CharField(
        max_length=80,
        default="Learn. Create. Indulge.",
        verbose_name="Script line at the top",
    )
    hero_title = models.CharField(
        max_length=40,
        default="Tiramisu",
        verbose_name="Big title on the flyer",
    )
    hero_kicker = models.CharField(
        max_length=80,
        default="Making Workshop",
        verbose_name="Small title under the big word",
    )
    gold_banner = models.CharField(
        max_length=80,
        default="Eggless tiramisu making",
        verbose_name="Gold banner line",
    )
    take_home_intro = models.CharField(
        max_length=80,
        default="What you will take home?",
        verbose_name="Take-home heading",
    )
    take_home_list = models.TextField(
        default=DEFAULT_TAKE_HOME,
        verbose_name="What guests take home",
        help_text="One item per line. These show on the public flyer.",
    )
    limited_seats_line = models.CharField(
        max_length=120,
        default="Limited seats. Book your spot now!",
        verbose_name="Limited seats line",
    )
    price_bar_label = models.CharField(
        max_length=80,
        default="Registration charges",
        verbose_name="Price bar label",
        help_text="Left side of the magenta price bar on the flyer.",
    )
    cta_label = models.CharField(
        max_length=40,
        default="Book your spot now",
        verbose_name="Flyer button label",
        help_text="The green Book button on the homepage flyer. The Event form button uses the same label.",
    )
    price_per_seat = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1499.00"),
        verbose_name="Price per seat (₹)",
    )
    max_seats_per_booking = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Max seats one guest can book",
        help_text="Used only when this event has no packages (fallback seat picker).",
    )
    seat_capacity = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        verbose_name="Total seats for this event",
        help_text="Sold out when paid bookings reach this number. Pending payments do not hold a seat.",
    )
    description = RichTextField(
        blank=True,
        verbose_name="Extra details",
        help_text="Optional extra details under the event facts.",
    )
    form_note = models.TextField(
        verbose_name="Note under the booking form",
        default=(
            "After submitting this form, you will receive your secure payment link. "
            "Your seat will be confirmed only after successful payment."
        ),
    )
    hero_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Hero image",
    )
    enquiry_whatsapp = models.CharField(
        max_length=16,
        default=DEFAULT_ENQUIRY_WHATSAPP,
        blank=True,
        verbose_name="Enquiry WhatsApp number",
        help_text="10-digit Indian number shown on the flyer. Leave blank to hide the enquiry link.",
    )
    group_invite_link = models.URLField(
        blank=True,
        verbose_name="WhatsApp group invite link",
        help_text="Paste the group invite. Sent only after payment — we never force-add anyone.",
    )
    payment_link_url = models.URLField(
        blank=True,
        verbose_name="Fallback Razorpay payment link (per seat)",
        help_text=(
            "Last-resort only if Razorpay API keys are missing and this event has no packages. "
            "When keys are set, checkout always creates a unique Payment Link."
        ),
    )
    payment_description = models.CharField(
        max_length=180,
        default="Cafe Orelo workshop",
        verbose_name="Payment link description",
        help_text="Shown on the unique Razorpay Payment Link. The booking reference is added automatically.",
    )
    reference_prefix = models.CharField(
        max_length=24,
        default="ORELO",
        verbose_name="Booking reference prefix",
        help_text="Used in payment references, e.g. ORELO-20260823-001.",
    )
    confirmation_template = models.TextField(
        verbose_name="WhatsApp message after payment",
        help_text=(
            "Placeholders: {{name}}, {{event}}, {{group_invite_link}}, {{amount}}, "
            "{{date}}, {{time}}, {{venue}}, {{chef}}, {{reference}}, {{seats}}"
        ),
        default=DEFAULT_CONFIRMATION,
    )
    reminder_hours_before = models.PositiveSmallIntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(168)],
        verbose_name="Reminder hours before start",
        help_text=(
            "Send the reminder this many hours before the event start "
            "(email + WhatsApp). Default 24. Vercel cron runs daily at 15:00 IST."
        ),
    )
    reminder_template = models.TextField(
        verbose_name="Reminder message (WhatsApp + email)",
        default=DEFAULT_REMINDER,
        help_text=(
            "Used for both WhatsApp and the reminder email body. Same placeholders "
            "as the confirmation message, plus {{package}}."
        ),
    )
    reminder_email_subject = models.CharField(
        max_length=180,
        default=DEFAULT_REMINDER_EMAIL_SUBJECT,
        verbose_name="Reminder email subject",
        help_text="Same placeholders as the reminder message.",
    )
    email_subject = models.CharField(
        max_length=180,
        default=DEFAULT_EMAIL_SUBJECT,
        verbose_name="Email subject after payment",
        help_text="Same placeholders as the email body.",
    )
    email_body = models.TextField(
        default=DEFAULT_EMAIL_BODY,
        verbose_name="Email sent after payment",
        help_text=(
            "Sent after payment with the WhatsApp group invite. Placeholders: "
            "{{name}}, {{event}}, {{date}}, {{time}}, {{venue}}, {{chef}}, "
            "{{group_invite_link}}, {{invite_link}}, {{amount}}, {{reference}}, "
            "{{seats}}, {{package}}"
        ),
    )

    content_panels = Page.content_panels + [
        HelpPanel(content=EVENT_HELP, heading="Before you publish"),
        MultiFieldPanel(
            [
                FieldPanel("workshop_subtitle"),
                FieldPanel("workshop_date"),
                FieldPanel("start_time"),
                FieldPanel("end_time"),
                FieldPanel("venue"),
                FieldPanel("chef_name"),
                FieldPanel("hero_image"),
                FieldPanel("description"),
            ],
            heading="Event",
        ),
        MultiFieldPanel(
            [
                FieldPanel("tagline"),
                FieldPanel("hero_title"),
                FieldPanel("hero_kicker"),
                FieldPanel("gold_banner"),
                FieldPanel("take_home_intro"),
                FieldPanel("take_home_list"),
                FieldPanel("limited_seats_line"),
                FieldPanel("price_bar_label"),
                FieldPanel("cta_label"),
                FieldPanel("enquiry_whatsapp"),
            ],
            heading="Flyer copy (this Event page)",
        ),
        InlinePanel(
            "packages",
            heading="Packages — add, delete, reorder",
            label="package",
            min_num=0,
            max_num=20,
            classname="workshop-packages-panel",
            help_text=PACKAGE_HELP,
        ),
        MultiFieldPanel(
            [
                FieldPanel("price_per_seat"),
                FieldPanel("max_seats_per_booking"),
                FieldPanel("seat_capacity"),
                FieldPanel("form_note"),
                FieldPanel("payment_link_url"),
                FieldPanel("payment_description"),
                FieldPanel("reference_prefix"),
            ],
            heading="Registration & payment",
        ),
        MultiFieldPanel(
            [
                FieldPanel("group_invite_link"),
                FieldPanel("confirmation_template"),
            ],
            heading="WhatsApp",
        ),
        MultiFieldPanel(
            [
                FieldPanel("email_subject"),
                FieldPanel("email_body"),
            ],
            heading="Email sent after payment",
        ),
        MultiFieldPanel(
            [
                FieldPanel("reminder_hours_before"),
                FieldPanel("reminder_template"),
                FieldPanel("reminder_email_subject"),
            ],
            heading="Reminders",
        ),
    ]

    parent_page_types = ["workshop.HomePage"]
    subpage_types = []

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"

    def serve(self, request, *args, **kwargs):
        from .views import register

        result = register(request, self)
        if not isinstance(result, dict):
            return result
        request._registration_form = result["form"]
        return super().serve(request, *args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        from workshop import seo

        from .forms import RegistrationForm

        context = super().get_context(request, *args, **kwargs)
        context["form"] = getattr(request, "_registration_form", None) or RegistrationForm(self)
        context["seat_choices"] = self.seat_choices()
        context["booking_configured"] = self.booking_is_configured()
        context["has_bookable_package"] = self.has_bookable_package()
        context["canonical_url"] = seo.page_canonical(self)
        context["og_type"] = "event"
        context["og_image_url"] = seo.og_image_for_workshop(self)
        context["robots"] = "index, follow, max-image-preview:large"
        context["seo_title"] = self.seo_title or seo.default_title(self)
        context["seo_description"] = self.search_description or seo.default_description(self)
        context["og_image_alt"] = (
            f"{self.workshop_subtitle} at {self.venue} with Chef {self.chef_display_name()}, "
            f"{self.format_date()}, {self.format_time_range()}, {seo.price_label(self)}"
        )
        context["event_json_ld"] = seo.json_ld_script(
            seo.graph_payload(seo.event_json_ld(self, canonical=context["canonical_url"]))
        )
        return context

    def _api_checkout_available(self) -> bool:
        from django.conf import settings

        from .razorpay_client import has_api_keys

        return has_api_keys() or bool(settings.RAZORPAY_MOCK)

    def bookable_packages(self) -> list["WorkshopPackage"]:
        remaining = self.seats_remaining()
        api_ok = self._api_checkout_available()
        return [
            package
            for package in self.packages.all()
            if package.is_usable()
            and package.seats <= remaining
            and (api_ok or package.has_payment_link())
        ]

    def booking_is_configured(self) -> bool:
        if self._api_checkout_available():
            return True
        if self.packages.exists():
            return any((package.payment_link or "").strip() for package in self.packages.all())
        return bool((self.payment_link_url or "").strip())

    def has_bookable_package(self) -> bool:
        if self.packages.exists():
            return bool(self.bookable_packages())
        return self.booking_is_configured() and self.seats_remaining() > 0

    def starting_price(self) -> Decimal:
        prices = [package.price for package in self.packages.all() if package.is_usable()]
        if prices:
            return min(prices)
        return self.price_per_seat

    def seat_choices(self) -> list[tuple[int, Decimal, str]]:
        """Fallback 1…N seat picker when this event has no packages."""
        choices = []
        for seats in range(1, self.max_seats_per_booking + 1):
            amount = (self.price_per_seat * seats).quantize(Decimal("0.01"))
            label = f"{seats} Seat{'s' if seats != 1 else ''} — ₹{amount:,.0f}"
            choices.append((seats, amount, label))
        return choices

    def paid_seats(self) -> int:
        total = self.registrations.filter(status=RegistrationStatus.PAID).aggregate(
            total=models.Sum("seats")
        )["total"]
        return int(total or 0)

    def seats_remaining(self) -> int:
        return max(0, int(self.seat_capacity) - self.paid_seats())

    def is_sold_out(self) -> bool:
        return self.seats_remaining() <= 0

    def uses_static_payment_link(self) -> bool:
        """True when guests pay the event-level per-seat URL (no packages)."""
        return not self.packages.exists() and bool((self.payment_link_url or "").strip())

    def payment_link_description(self, reference_id: str) -> str:
        base = (self.payment_description or self.title or "Cafe Orelo workshop").strip()
        title = (self.title or "").strip()
        if title and title.lower() not in base.lower():
            base = f"{base} · {title}"
        description = f"{base} · {reference_id}"
        return description[:255]

    def next_reference_id(self) -> str:
        date_part = self.workshop_date.strftime("%Y%m%d")
        prefix = f"{self.reference_prefix}-{date_part}-"
        last = (
            Registration.objects.filter(workshop=self, reference_id__startswith=prefix)
            .order_by("-reference_id")
            .values_list("reference_id", flat=True)
            .first()
        )
        sequence = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
        return f"{prefix}{sequence:03d}"


class WorkshopPackage(Orderable):
    """One bookable option on an Event — name, seats, price, and its Razorpay link."""

    page = ParentalKey(
        "workshop.WorkshopPage",
        on_delete=models.CASCADE,
        related_name="packages",
    )
    name = models.CharField(
        max_length=80,
        verbose_name="Package name",
        help_text="e.g. “1 Seat”, “2 Seats”, “Couple”.",
    )
    seats = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        verbose_name="Seats included",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1.00"))],
        verbose_name="Price (₹)",
        help_text="INR, rupees. Shown as ₹ on the public form.",
    )
    payment_link = models.URLField(
        blank=True,
        verbose_name="Razorpay payment link",
        help_text=(
            "Unused for checkout when Razorpay API keys are set — we create a unique "
            "Payment Link per booking. Last-resort fallback only if keys are missing."
        ),
    )
    note = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Short note",
        help_text="Optional. Shown next to the package on the public form.",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("seats"),
        FieldPanel("price"),
        FieldPanel("payment_link"),
        FieldPanel("note"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = "Package"
        verbose_name_plural = "Packages"

    def __str__(self) -> str:
        return f"{self.name} · {self.seats} seat{'s' if self.seats != 1 else ''} · ₹{self.price:,.0f}"

    def public_label(self) -> str:
        label = f"{self.name} — ₹{self.price:,.0f}"
        note = (self.note or "").strip()
        if note:
            label = f"{label} · {note}"
        return label

    def has_payment_link(self) -> bool:
        return bool((self.payment_link or "").strip())

    def is_usable(self) -> bool:
        """Public form needs a real seat count and a price of at least ₹1."""
        return int(self.seats or 0) >= 1 and self.price is not None and self.price >= 1


class RegistrationStatus(models.TextChoices):
    PAYMENT_PENDING = "PAYMENT_PENDING", "Payment pending"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    EXPIRED = "EXPIRED", "Expired"


class Registration(models.Model):
    """Participant row — the portal equivalent of the spec Google Sheet."""

    workshop = models.ForeignKey(
        WorkshopPage,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="Event",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Registered at",
        help_text="Set automatically when the guest submits the form. Shown in IST.",
    )
    full_name = models.CharField(max_length=120)
    whatsapp = models.CharField(max_length=15)
    email = models.EmailField()
    seats = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    package = models.ForeignKey(
        WorkshopPackage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registrations",
        verbose_name="Package",
    )
    package_name = models.CharField(max_length=80, blank=True, verbose_name="Package name")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_link = models.URLField(blank=True)
    payment_link_id = models.CharField(max_length=40, blank=True, db_index=True)
    payment_id = models.CharField(max_length=40, blank=True)
    reference_id = models.CharField(max_length=40, unique=True)
    status = models.CharField(
        max_length=24,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.PAYMENT_PENDING,
        db_index=True,
    )
    group_invite_sent = models.BooleanField(
        default=False,
        verbose_name="WhatsApp invite sent",
    )
    email_invite_sent = models.BooleanField(
        default=False,
        verbose_name="Email invite sent",
    )
    reminder_sent = models.BooleanField(default=False, verbose_name="Reminder sent")
    raw_webhook = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.full_name} · {self.reference_id} · {self.status}"

    def registered_at_ist(self) -> str:
        return format_ist(self.created_at)

    registered_at_ist.short_description = "Registered (IST)"
    registered_at_ist.admin_order_field = "created_at"

    def status_label(self) -> str:
        return self.get_status_display()

    status_label.short_description = "Status"
    status_label.admin_order_field = "status"

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            previous_status = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
        super().save(*args, **kwargs)
        became_paid = (
            self.status == RegistrationStatus.PAID
            and previous_status != RegistrationStatus.PAID
        )
        if became_paid:
            from .payments import confirm_paid

            confirm_paid(self, self.payment_id or "admin")

    @property
    def amount_paise(self) -> int:
        return int(self.amount * 100)

    def group_invite_label(self) -> str:
        return "Yes" if self.group_invite_sent else "No"

    group_invite_label.short_description = "WhatsApp sent"
    group_invite_label.admin_order_field = "group_invite_sent"
    group_invite_label.boolean = False

    def email_invite_label(self) -> str:
        return "Yes" if self.email_invite_sent else "No"

    email_invite_label.short_description = "Email sent"
    email_invite_label.admin_order_field = "email_invite_sent"

    def reminder_label(self) -> str:
        return "Yes" if self.reminder_sent else "No"

    reminder_label.short_description = "Reminder sent"
    reminder_label.admin_order_field = "reminder_sent"

    @property
    def package_label(self) -> str:
        if self.package_name:
            return self.package_name
        if self.package_id:
            return self.package.name
        return "—"

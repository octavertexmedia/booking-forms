from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.images import get_image_model_string
from wagtail.models import Page


class HomePage(Page):
    """Cafe landing page that points visitors at the current workshop."""

    intro = RichTextField(
        blank=True,
        help_text="Short welcome copy shown above the workshop card.",
    )
    hero_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("hero_image"),
    ]

    max_count = 1

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["workshop"] = (
            WorkshopPage.objects.live().descendant_of(self).order_by("workshop_date").first()
        )
        return context


class WorkshopPage(Page):
    """CMS-editable workshop landing + registration form."""

    workshop_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=120, default="Cafe Orelo")
    chef_name = models.CharField(max_length=120, default="Aanchal Wadhwa")
    workshop_subtitle = models.CharField(
        max_length=160,
        default="Eggless Tiramisu Making Workshop",
        help_text="Shown on the page and in WhatsApp messages.",
    )
    price_per_seat = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1499.00"),
    )
    max_seats_per_booking = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    description = RichTextField(
        blank=True,
        help_text="Optional extra details under the event facts.",
    )
    form_note = models.TextField(
        default=(
            "After submitting this form, you will receive your secure payment link. "
            "Your seat will be confirmed only after successful payment."
        )
    )
    hero_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    group_invite_link = models.URLField(
        blank=True,
        help_text="WhatsApp group invite. Sent only after payment — never force-added.",
    )
    payment_description = models.CharField(
        max_length=180,
        default="Cafe Orelo - Tiramisu Making Workshop",
    )
    reference_prefix = models.CharField(max_length=24, default="TIRAMISU")
    confirmation_template = models.TextField(
        help_text="Placeholders: {{name}}, {{group_invite_link}}, {{amount}}, {{date}}, {{time}}, {{venue}}, {{chef}}",
        default=(
            "🎉 Registration Confirmed!\n\n"
            "Hi {{name}} 👋\n\n"
            "Your registration for the Eggless Tiramisu Making Workshop at Cafe Orelo is confirmed! 🍰\n\n"
            "📅 {{date}}\n"
            "⏰ {{time}}\n"
            "📍 {{venue}}\n"
            "👩‍🍳 {{chef}}\n\n"
            "💳 Payment: ₹{{amount}} — PAID\n\n"
            "👥 Join the workshop WhatsApp group:\n"
            "{{group_invite_link}}\n\n"
            "We’ll share all workshop updates and important details in the group.\n\n"
            "See you at Cafe Orelo! 🤎"
        ),
    )
    reminder_template = models.TextField(
        default=(
            "🍰 Your Tiramisu Workshop is tomorrow!\n\n"
            "We're excited to see you at Cafe Orelo tomorrow from 3–5 PM.\n\n"
            "Please arrive 10 minutes early.\n\n"
            "See you tomorrow! 🤎"
        )
    )

    content_panels = Page.content_panels + [
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
            heading="Workshop",
        ),
        MultiFieldPanel(
            [
                FieldPanel("price_per_seat"),
                FieldPanel("max_seats_per_booking"),
                FieldPanel("form_note"),
                FieldPanel("payment_description"),
                FieldPanel("reference_prefix"),
            ],
            heading="Registration & payment",
        ),
        MultiFieldPanel(
            [
                FieldPanel("group_invite_link"),
                FieldPanel("confirmation_template"),
                FieldPanel("reminder_template"),
            ],
            heading="WhatsApp",
        ),
    ]

    parent_page_types = ["workshop.HomePage"]
    subpage_types = []

    def serve(self, request, *args, **kwargs):
        from .views import register

        result = register(request, self)
        if not isinstance(result, dict):
            return result
        request._registration_form = result["form"]
        return super().serve(request, *args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        from .forms import RegistrationForm

        context = super().get_context(request, *args, **kwargs)
        context["form"] = getattr(request, "_registration_form", None) or RegistrationForm(self)
        context["seat_choices"] = self.seat_choices()
        return context

    def seat_choices(self) -> list[tuple[int, Decimal, str]]:
        choices = []
        for seats in range(1, self.max_seats_per_booking + 1):
            amount = (self.price_per_seat * seats).quantize(Decimal("0.01"))
            label = f"{seats} Seat{'s' if seats != 1 else ''} — ₹{amount:,.0f}"
            choices.append((seats, amount, label))
        return choices

    def format_date(self) -> str:
        return self.workshop_date.strftime("%-d %B %Y")

    def format_time_range(self) -> str:
        start = self.start_time.strftime("%-I:%M %p").replace("AM", "AM").replace("PM", "PM")
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
    )
    created_at = models.DateTimeField(default=timezone.now)
    full_name = models.CharField(max_length=120)
    whatsapp = models.CharField(max_length=15)
    email = models.EmailField()
    seats = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
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
    group_invite_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    raw_webhook = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.full_name} · {self.reference_id} · {self.status}"

    @property
    def amount_paise(self) -> int:
        return int(self.amount * 100)

    @property
    def group_invite_label(self) -> str:
        return "YES" if self.group_invite_sent else "NO"

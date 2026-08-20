import re

from django import forms

from .models import WorkshopPackage, WorkshopPage

PHONE_RE = re.compile(r"^(?:\+91[\s-]?)?[6-9]\d{9}$")


class PackageChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: WorkshopPackage) -> str:
        return obj.public_label()


class RegistrationForm(forms.Form):
    full_name = forms.CharField(
        label="Full name",
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "name",
                "placeholder": "As you’d like it on the guest list",
            }
        ),
    )
    whatsapp = forms.CharField(
        label="WhatsApp number",
        max_length=16,
        widget=forms.TextInput(
            attrs={
                "inputmode": "tel",
                "autocomplete": "tel",
                "placeholder": "10-digit Indian mobile",
            }
        ),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "you@email.com",
            }
        ),
    )
    seats = forms.TypedChoiceField(
        label="Number of seats",
        coerce=int,
        widget=forms.RadioSelect,
        required=False,
    )
    package = PackageChoiceField(
        label="Number of seats / package",
        queryset=WorkshopPackage.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        required=False,
    )

    def __init__(self, workshop: WorkshopPage, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workshop = workshop
        remaining = workshop.seats_remaining()
        if workshop.packages.exists():
            del self.fields["seats"]
            bookable = workshop.bookable_packages()
            self.fields["package"].queryset = WorkshopPackage.objects.filter(
                pk__in=[package.pk for package in bookable]
            ).order_by("sort_order")
            self.fields["package"].required = True
        else:
            del self.fields["package"]
            self.fields["seats"].choices = [
                (seats, label)
                for seats, _amount, label in workshop.seat_choices()
                if seats <= remaining
            ]
            self.fields["seats"].required = True
        for name, field in self.fields.items():
            if name in {"seats", "package"}:
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} field-input".strip()
            field.widget.attrs["required"] = True

    def clean_full_name(self) -> str:
        name = self.cleaned_data["full_name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Enter your full name.")
        return name

    def clean_whatsapp(self) -> str:
        raw = re.sub(r"[\s-]", "", self.cleaned_data["whatsapp"])
        if not PHONE_RE.match(raw):
            raise forms.ValidationError("Enter a valid 10-digit Indian WhatsApp number.")
        digits = raw[-10:]
        return digits

    def clean_package(self) -> WorkshopPackage | None:
        package = self.cleaned_data.get("package")
        if "package" not in self.fields:
            return None
        if package is None:
            raise forms.ValidationError("Choose a package.")
        remaining = self.workshop.seats_remaining()
        if remaining <= 0:
            raise forms.ValidationError("This event is sold out.")
        live = self.workshop.packages.filter(pk=package.pk).first()
        if live is None or not live.has_payment_link():
            raise forms.ValidationError("Choose an available package.")
        if live.seats > remaining:
            raise forms.ValidationError(
                f"Only {remaining} seat{'s' if remaining != 1 else ''} left for this event."
            )
        return live

    def clean_seats(self) -> int | None:
        if "seats" not in self.fields:
            return None
        seats = self.cleaned_data.get("seats")
        remaining = self.workshop.seats_remaining()
        if remaining <= 0:
            raise forms.ValidationError("This event is sold out.")
        if seats is None or seats < 1 or seats > self.workshop.max_seats_per_booking:
            raise forms.ValidationError("Choose an available seat option.")
        if seats > remaining:
            raise forms.ValidationError(
                f"Only {remaining} seat{'s' if remaining != 1 else ''} left for this event."
            )
        return seats

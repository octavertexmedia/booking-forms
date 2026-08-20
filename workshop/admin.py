import csv

from django.contrib import admin, messages
from django.http import HttpResponse

from .models import Registration, RegistrationStatus
from .payments import confirm_paid


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "workshop",
        "full_name",
        "package_name",
        "seats",
        "status",
        "payment_id",
        "email_invite_label",
        "group_invite_label",
        "reminder_label",
        "reference_id",
    )
    list_filter = (
        "workshop",
        "status",
        "email_invite_sent",
        "group_invite_sent",
        "reminder_sent",
    )
    search_fields = ("full_name", "email", "whatsapp", "reference_id", "payment_id")
    readonly_fields = ("created_at", "reference_id", "payment_link_id", "raw_webhook")
    actions = ["mark_as_paid", "export_sheet_csv"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == RegistrationStatus.PAID:
            confirm_paid(obj, obj.payment_id or "admin")

    @admin.action(description="Mark as paid (send WhatsApp + email invite)")
    def mark_as_paid(self, request, queryset):
        count = 0
        for row in queryset:
            confirm_paid(row, row.payment_id or "admin")
            count += 1
        self.message_user(
            request,
            f"Marked {count} registration{'s' if count != 1 else ''} as paid and sent invites if needed.",
            messages.SUCCESS,
        )

    @admin.display(description="WhatsApp sent")
    def group_invite_label(self, obj: Registration) -> str:
        return obj.group_invite_label

    @admin.display(description="Email sent")
    def email_invite_label(self, obj: Registration) -> str:
        return obj.email_invite_label

    @admin.display(description="Reminder sent")
    def reminder_label(self, obj: Registration) -> str:
        return obj.reminder_label

    @admin.action(description="Export sheet CSV")
    def export_sheet_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="workshop-registrations.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Timestamp",
                "Event",
                "Name",
                "WhatsApp",
                "Email",
                "Package",
                "Seats",
                "Amount",
                "Payment Link",
                "Payment ID",
                "Status",
                "WhatsApp Invite Sent",
                "Email Invite Sent",
                "Reminder Sent",
            ]
        )
        for row in queryset.select_related("workshop").order_by("created_at"):
            writer.writerow(
                [
                    row.created_at.strftime("%d %b %Y %H:%M"),
                    row.workshop.title,
                    row.full_name,
                    row.whatsapp,
                    row.email,
                    row.package_label,
                    row.seats,
                    f"₹{row.amount:,.0f}",
                    row.payment_link,
                    row.payment_id or "—",
                    row.status,
                    row.group_invite_label,
                    row.email_invite_label,
                    row.reminder_label,
                ]
            )
        return response

import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import Registration


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "workshop",
        "full_name",
        "seats",
        "status",
        "payment_id",
        "group_invite_label",
        "email_invite_label",
        "reference_id",
    )
    list_filter = ("workshop", "status", "group_invite_sent", "email_invite_sent")
    search_fields = ("full_name", "email", "whatsapp", "reference_id", "payment_id")
    readonly_fields = ("created_at", "reference_id", "payment_link_id", "raw_webhook")
    actions = ["export_sheet_csv"]

    @admin.display(description="WhatsApp invite sent")
    def group_invite_label(self, obj: Registration) -> str:
        return obj.group_invite_label

    @admin.display(description="Email invite sent")
    def email_invite_label(self, obj: Registration) -> str:
        return obj.email_invite_label

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
                "Seats",
                "Amount",
                "Payment Link",
                "Payment ID",
                "Status",
                "WhatsApp Invite Sent",
                "Email Invite Sent",
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
                    row.seats,
                    f"₹{row.amount:,.0f}",
                    row.payment_link,
                    row.payment_id or "—",
                    row.status,
                    row.group_invite_label,
                    row.email_invite_label,
                ]
            )
        return response

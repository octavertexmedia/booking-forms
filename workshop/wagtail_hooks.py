from django.contrib import admin
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.views.home import UpgradeNotificationPanel
from wagtail.admin.widgets.button import ListingButton
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Registration, RegistrationStatus
from .payments import confirm_paid

admin.site.site_header = "Cafe Orelo Booking Forms"
admin.site.site_title = "Cafe Orelo"
admin.site.index_title = "Workshop admin"


@hooks.register("insert_global_admin_css")
def global_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}?v=20260820-packages">',
        static("workshop/css/admin.css"),
    )


@hooks.register("construct_homepage_panels")
def hide_wagtail_upgrade_panel(request, panels):
    panels[:] = [panel for panel in panels if not isinstance(panel, UpgradeNotificationPanel)]


class RegistrationViewSet(SnippetViewSet):
    model = Registration
    menu_label = "Registrations"
    icon = "user"
    menu_order = 150
    list_display = (
        "workshop",
        "full_name",
        "package_name",
        "seats",
        "status",
        "payment_id",
        "email_invite_sent",
        "group_invite_sent",
        "reminder_sent",
        "reference_id",
    )
    list_filter = (
        "workshop",
        "status",
        "email_invite_sent",
        "group_invite_sent",
        "reminder_sent",
    )
    search_fields = ("full_name", "email", "whatsapp", "reference_id", "payment_id", "package_name")
    list_export = (
        "created_at",
        "workshop",
        "full_name",
        "whatsapp",
        "email",
        "package_name",
        "seats",
        "amount",
        "payment_link",
        "payment_id",
        "status",
        "group_invite_sent",
        "email_invite_sent",
        "reminder_sent",
        "reference_id",
    )
    export_filename = "cafe-orelo-registrations"
    inspect_view_enabled = True
    add_to_admin_menu = True


register_snippet(RegistrationViewSet)


@hooks.register("register_snippet_listing_buttons")
def registration_listing_buttons(snippet, user, next_url=None, **kwargs):
    if not isinstance(snippet, Registration):
        return
    if snippet.status == RegistrationStatus.PAID:
        return
    if not user.has_perm("workshop.change_registration"):
        return
    yield ListingButton(
        "Mark as paid",
        reverse("admin_mark_paid", args=[snippet.pk]),
        priority=10,
    )


@hooks.register("after_edit_snippet")
def send_invites_when_marked_paid(request, instance):
    if isinstance(instance, Registration) and instance.status == RegistrationStatus.PAID:
        confirm_paid(instance, instance.payment_id or "admin")

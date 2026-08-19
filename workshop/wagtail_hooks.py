from django.contrib import admin
from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.views.home import UpgradeNotificationPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Registration

admin.site.site_header = "Cafe Orelo Booking Forms"
admin.site.site_title = "Cafe Orelo"
admin.site.index_title = "Workshop admin"


@hooks.register("insert_global_admin_css")
def global_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}?v=20260819-cta">',
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
        "seats",
        "status",
        "payment_id",
        "group_invite_sent",
        "email_invite_sent",
        "reference_id",
    )
    list_filter = ("workshop", "status", "group_invite_sent", "email_invite_sent")
    search_fields = ("full_name", "email", "whatsapp", "reference_id", "payment_id")
    list_export = (
        "created_at",
        "workshop",
        "full_name",
        "whatsapp",
        "email",
        "seats",
        "amount",
        "payment_link",
        "payment_id",
        "status",
        "group_invite_sent",
        "email_invite_sent",
        "reference_id",
    )
    export_filename = "cafe-orelo-registrations"
    inspect_view_enabled = True
    add_to_admin_menu = True


register_snippet(RegistrationViewSet)

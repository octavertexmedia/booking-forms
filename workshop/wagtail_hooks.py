from django.contrib import admin
from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Registration

admin.site.site_header = "Cafe Orelo Workshops"
admin.site.site_title = "Cafe Orelo"
admin.site.index_title = "Workshop admin"


@hooks.register("insert_global_admin_css")
def global_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}">',
        static("workshop/css/admin.css"),
    )


class RegistrationViewSet(SnippetViewSet):
    model = Registration
    menu_label = "Registrations"
    icon = "user"
    menu_order = 150
    list_display = (
        "created_at",
        "full_name",
        "whatsapp",
        "email",
        "seats",
        "amount",
        "status",
        "group_invite_sent",
        "reference_id",
    )
    list_filter = ("status", "group_invite_sent", "workshop")
    search_fields = ("full_name", "email", "whatsapp", "reference_id", "payment_id")
    inspect_view_enabled = True
    add_to_admin_menu = True


register_snippet(RegistrationViewSet)

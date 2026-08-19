"""Shared placeholder rendering for WhatsApp and email templates."""

from __future__ import annotations

from .models import Registration, WorkshopPage


def message_context(workshop: WorkshopPage, registration: Registration) -> dict[str, str]:
    invite = workshop.group_invite_link or "(invite link not set yet)"
    event_name = workshop.workshop_subtitle or workshop.title
    return {
        "{{name}}": registration.full_name,
        "{{event}}": event_name,
        "{{event_title}}": workshop.title,
        "{{group_invite_link}}": invite,
        "{{invite_link}}": invite,
        "{{amount}}": f"{registration.amount:,.0f}",
        "{{date}}": workshop.format_date(),
        "{{time}}": workshop.format_time_range(),
        "{{venue}}": workshop.venue,
        "{{chef}}": workshop.chef_name,
        "{{reference}}": registration.reference_id,
        "{{seats}}": str(registration.seats),
    }


def render_template(template: str, workshop: WorkshopPage, registration: Registration) -> str:
    message = template or ""
    for key, value in message_context(workshop, registration).items():
        message = message.replace(key, value)
    return message

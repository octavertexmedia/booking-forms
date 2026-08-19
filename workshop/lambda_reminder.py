"""EventBridge-triggered Saturday reminder (same container image as the web function)."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portal.settings.serverless")
django.setup()

from django.core.management import call_command  # noqa: E402


def handler(event, context):
    call_command("send_workshop_reminders")
    return {"ok": True}

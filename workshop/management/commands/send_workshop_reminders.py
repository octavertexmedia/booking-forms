from django.core.management.base import BaseCommand

from workshop.reminders import send_due_reminders


class Command(BaseCommand):
    help = (
        "Send email + WhatsApp reminders to PAID guests whose event starts "
        "within the Event’s reminder-hours window."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Send to every unpaid-reminder PAID registration, ignoring the window.",
        )

    def handle(self, *args, **options):
        result = send_due_reminders(force=options["force"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders sent: {result['sent']}. "
                f"Failed or skipped: {result['skipped']}."
            )
        )

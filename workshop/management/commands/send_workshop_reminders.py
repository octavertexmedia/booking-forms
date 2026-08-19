from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from workshop.models import Registration, RegistrationStatus
from workshop.whatsapp import send_reminder


class Command(BaseCommand):
    help = "Send the Saturday-evening reminder to paid guests whose workshop is tomorrow."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Send to every unpaid-reminder PAID registration, ignoring the date check.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        qs = Registration.objects.filter(
            status=RegistrationStatus.PAID,
            reminder_sent=False,
        ).select_related("workshop")
        if not options["force"]:
            qs = qs.filter(workshop__workshop_date=today + timedelta(days=1))

        sent = 0
        skipped = 0
        for registration in qs:
            if send_reminder(registration):
                sent += 1
            else:
                skipped += 1
        self.stdout.write(
            self.style.SUCCESS(f"Reminders sent: {sent}. Failed or skipped: {skipped}.")
        )

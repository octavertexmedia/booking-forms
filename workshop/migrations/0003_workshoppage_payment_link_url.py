from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workshop", "0002_event_email_and_capacity"),
    ]

    operations = [
        migrations.AddField(
            model_name="workshoppage",
            name="payment_link_url",
            field=models.URLField(
                blank=True,
                help_text=(
                    "Shared rzp.io (or Razorpay) URL priced for one seat. After submit, guests are "
                    "sent here. If they book 2–3 seats they must pay this same link once per seat. "
                    "Leave blank to create a unique Payment Link for price × seats when API keys are set."
                ),
                verbose_name="Razorpay payment link (per seat)",
            ),
        ),
    ]

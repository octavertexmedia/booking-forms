from datetime import date, time
from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


DEFAULT_TAKE_HOME = (
    "Your own handmade eggless tiramisu\n"
    "Detailed recipe sheet\n"
    "Hands-on learning & techniques\n"
    "Complimentary beverage\n"
    "A fun baking experience with fellow dessert lovers"
)

COPY_FIELDS = (
    "tagline",
    "hero_title",
    "hero_kicker",
    "gold_banner",
    "take_home_intro",
    "take_home_list",
    "limited_seats_line",
    "price_bar_label",
    "cta_label",
    "enquiry_whatsapp",
    "chef_name",
    "workshop_date",
    "start_time",
    "end_time",
    "venue",
    "price_per_seat",
)


def copy_event_flyer_to_home(apps, schema_editor):
    HomePage = apps.get_model("workshop", "HomePage")
    WorkshopPage = apps.get_model("workshop", "WorkshopPage")
    home = HomePage.objects.order_by("path").first()
    if not home:
        return
    event = (
        WorkshopPage.objects.filter(live=True).order_by("workshop_date").first()
        or WorkshopPage.objects.order_by("workshop_date").first()
    )
    if not event:
        return
    for field in COPY_FIELDS:
        setattr(home, field, getattr(event, field))
    home.save(update_fields=list(COPY_FIELDS))


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0007_home_listing_and_flyer_cta"),
    ]

    operations = [
        migrations.AddField(
            model_name="homepage",
            name="brand_tagline",
            field=models.CharField(
                default="good food, good mood.",
                help_text="Under the Cafe Orelo logo on every public page.",
                max_length=80,
                verbose_name="Header tagline",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="logo",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional. Leave blank to keep the Cafe Orelo wordmark.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtailimages.image",
                verbose_name="Header logo",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="footer_line",
            field=models.CharField(
                default="Cafe Orelo · seats confirmed only after payment",
                help_text="Top line of the public footer (above the Octavertex credit).",
                max_length=160,
                verbose_name="Footer line",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="tagline",
            field=models.CharField(
                default="Learn. Create. Indulge.",
                max_length=80,
                verbose_name="Script line at the top",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="hero_title",
            field=models.CharField(
                default="Tiramisu",
                max_length=40,
                verbose_name="Big title on the flyer",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="hero_kicker",
            field=models.CharField(
                default="Making Workshop",
                max_length=80,
                verbose_name="Small title under the big word",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="gold_banner",
            field=models.CharField(
                default="Eggless tiramisu making",
                max_length=80,
                verbose_name="Gold banner line",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="workshop_date",
            field=models.DateField(
                default=date(2026, 8, 23),
                verbose_name="Date on the flyer",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="start_time",
            field=models.TimeField(default=time(15, 0), verbose_name="Start time"),
        ),
        migrations.AddField(
            model_name="homepage",
            name="end_time",
            field=models.TimeField(default=time(17, 0), verbose_name="End time"),
        ),
        migrations.AddField(
            model_name="homepage",
            name="venue",
            field=models.CharField(
                default="Cafe Orelo",
                max_length=120,
                verbose_name="Location",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="date_label",
            field=models.CharField(default="Date", max_length=24, verbose_name="Date label"),
        ),
        migrations.AddField(
            model_name="homepage",
            name="time_label",
            field=models.CharField(default="Time", max_length=24, verbose_name="Time label"),
        ),
        migrations.AddField(
            model_name="homepage",
            name="location_label",
            field=models.CharField(
                default="Location",
                max_length=24,
                verbose_name="Location label",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="take_home_intro",
            field=models.CharField(
                default="What you will take home?",
                max_length=80,
                verbose_name="Take-home heading",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="take_home_list",
            field=models.TextField(
                default=DEFAULT_TAKE_HOME,
                help_text="One item per line. These show on the public homepage flyer.",
                verbose_name="What guests take home",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="price_bar_label",
            field=models.CharField(
                default="Registration charges",
                max_length=80,
                verbose_name="Price bar label",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="price_per_seat",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1499.00"),
                help_text="Magenta bar on the homepage. Publishing Home copies this onto the live Event.",
                max_digits=8,
                verbose_name="Price on the flyer (₹)",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="limited_seats_line",
            field=models.CharField(
                default="Limited seats. Book your spot now!",
                max_length=120,
                verbose_name="Limited seats line",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="sold_out_line",
            field=models.CharField(
                default="Sold out",
                help_text="Replaces the limited-seats line when the Event has no seats left.",
                max_length=80,
                verbose_name="Sold-out line",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="cta_label",
            field=models.CharField(
                default="Book your spot now",
                max_length=40,
                verbose_name="Book button label",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="enquiry_whatsapp",
            field=models.CharField(
                blank=True,
                default="7709818290",
                help_text="10-digit Indian number on the flyer. Leave blank to hide the link.",
                max_length=16,
                verbose_name="Enquiry WhatsApp number",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="chef_name",
            field=models.CharField(
                default="Aanchal Wadhwa",
                max_length=120,
                verbose_name="Chef name",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="chef_byline",
            field=models.CharField(
                default="By",
                max_length=24,
                verbose_name="Chef chip — small word",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="chef_role",
            field=models.CharField(
                default="Pastry Chef",
                max_length=40,
                verbose_name="Chef chip — role",
            ),
        ),
        migrations.RunPython(copy_event_flyer_to_home, noop),
    ]

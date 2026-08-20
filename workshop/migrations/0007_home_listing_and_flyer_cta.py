from django.db import migrations, models
import wagtail.fields


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0006_package_fk_set_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="homepage",
            name="listing_tagline",
            field=models.CharField(
                default="Learn. Create. Indulge.",
                help_text="Script line above the heading when several events are listed, or none are live.",
                max_length=80,
                verbose_name="Listing tagline",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="listing_title",
            field=models.CharField(
                default="Bookings",
                help_text="Big word on the multi-event homepage. Unused when one Event flyer is showing.",
                max_length=40,
                verbose_name="Listing title",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="listing_kicker",
            field=models.CharField(
                default="Cafe Orelo workshops",
                help_text="Small line under the listing title.",
                max_length=80,
                verbose_name="Listing kicker",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="empty_lede",
            field=models.CharField(
                default="No workshop is published yet. Check back shortly.",
                help_text="Shown when no Event is published.",
                max_length=180,
                verbose_name="Empty-state line",
            ),
        ),
        migrations.AddField(
            model_name="homepage",
            name="card_cta_label",
            field=models.CharField(
                default="Book your spot",
                help_text="Button on each event card when several events are live.",
                max_length=40,
                verbose_name="Card button label",
            ),
        ),
        migrations.AlterField(
            model_name="homepage",
            name="intro",
            field=wagtail.fields.RichTextField(
                blank=True,
                help_text=(
                    "Shown on the public homepage whenever this is filled — above the "
                    "single-event flyer, or above the card list when several events are live."
                ),
                verbose_name="Welcome line",
            ),
        ),
        migrations.AddField(
            model_name="workshoppage",
            name="price_bar_label",
            field=models.CharField(
                default="Registration charges",
                help_text="Left side of the magenta price bar on the flyer.",
                max_length=80,
                verbose_name="Price bar label",
            ),
        ),
        migrations.AddField(
            model_name="workshoppage",
            name="cta_label",
            field=models.CharField(
                default="Book your spot now",
                help_text="The green Book button on the homepage flyer. The Event form button uses the same label.",
                max_length=40,
                verbose_name="Flyer button label",
            ),
        ),
    ]

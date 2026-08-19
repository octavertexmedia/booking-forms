import os
from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from workshop.models import HomePage, WorkshopPage

FLYER_INTRO = ""
FLYER_SUBTITLE = "Eggless Tiramisu Making Workshop"
FLYER_DATE = date(2026, 8, 23)
FLYER_START = time(15, 0)
FLYER_END = time(17, 0)
FLYER_VENUE = "Cafe Orelo"
FLYER_CHEF = "Aanchal Wadhwa"
FLYER_PRICE = Decimal("1499.00")


class Command(BaseCommand):
    help = "Create the Cafe Orelo home + Tiramisu workshop pages and an admin user."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin12345")

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
        else:
            self.stdout.write(f"Superuser '{username}' already exists.")

        root = Page.get_first_root_node()
        home = HomePage.objects.first()
        if home is None:
            stale = Page.objects.filter(depth=2, slug__in={"home", "welcome"}).first()
            if stale and stale.specific_class is Page:
                stale.delete()
                root.refresh_from_db()
            home = HomePage(
                title="Cafe Orelo",
                slug="home",
                intro=FLYER_INTRO,
            )
            root.add_child(instance=home)
            home.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Published Cafe Orelo home page."))
        else:
            if home.intro != FLYER_INTRO:
                home.intro = FLYER_INTRO
                home.save_revision().publish()
                self.stdout.write(self.style.SUCCESS("Updated home intro to match the flyer."))
            elif not home.live:
                home.save_revision().publish()
            self.stdout.write("Home page already exists.")

        site = Site.objects.filter(is_default_site=True).first()
        if site:
            if site.root_page_id != home.id or site.site_name != "Cafe Orelo Workshops":
                site.root_page = home
                site.site_name = "Cafe Orelo Workshops"
                site.save()
        else:
            Site.objects.create(
                hostname="localhost",
                port=80,
                root_page=home,
                is_default_site=True,
                site_name="Cafe Orelo Workshops",
            )
            self.stdout.write(self.style.SUCCESS("Created default Wagtail site."))

        workshop = WorkshopPage.objects.filter(slug="tiramisu-workshop").first()
        flyer_fields = {
            "workshop_subtitle": FLYER_SUBTITLE,
            "workshop_date": FLYER_DATE,
            "start_time": FLYER_START,
            "end_time": FLYER_END,
            "venue": FLYER_VENUE,
            "chef_name": FLYER_CHEF,
            "price_per_seat": FLYER_PRICE,
            "title": "Tiramisu Making Workshop",
        }
        if workshop is None:
            workshop = WorkshopPage(
                slug="tiramisu-workshop",
                description="",
                **flyer_fields,
            )
            home.add_child(instance=workshop)
            workshop.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Published Tiramisu workshop page."))
        else:
            changed = False
            for key, value in flyer_fields.items():
                if getattr(workshop, key) != value:
                    setattr(workshop, key, value)
                    changed = True
            if changed:
                workshop.save_revision().publish()
                self.stdout.write(self.style.SUCCESS("Updated workshop page to match the flyer."))
            else:
                self.stdout.write("Workshop page already exists.")

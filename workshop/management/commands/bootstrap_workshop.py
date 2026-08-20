import os
from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from workshop.models import HomePage, WorkshopPackage, WorkshopPage

FLYER_INTRO = ""
FLYER_SUBTITLE = "Eggless Tiramisu Making Workshop"
HOME_SEO_TITLE = "Cafe Orelo Tiramisu Workshop | HealthyOme Bookings"
HOME_SEARCH_DESCRIPTION = (
    "Book Cafe Orelo's eggless Tiramisu Making Workshop with Chef Aanchal Wadhwa. "
    "Sunday 23 Aug 2026, 3–5 PM. ₹1499 per seat. Enquire on WhatsApp 7709818290."
)
WORKSHOP_SEO_TITLE = "Tiramisu Making Workshop | Cafe Orelo"
WORKSHOP_SEARCH_DESCRIPTION = (
    "Eggless Tiramisu Making Workshop at Cafe Orelo with Chef Aanchal Wadhwa. "
    "Sunday 23 Aug 2026, 3–5 PM. ₹1499 per seat. Enquire on WhatsApp 7709818290. Book now."
)
FLYER_DATE = date(2026, 8, 23)
FLYER_START = time(15, 0)
FLYER_END = time(17, 0)
FLYER_VENUE = "Cafe Orelo"
FLYER_CHEF = "Aanchal Wadhwa"
FLYER_PRICE = Decimal("1499.00")
TIRAMISU_PAYMENT_LINK = "https://rzp.io/rzp/CW6o0Mec"
TIRAMISU_PACKAGES = (
    {
        "name": "1 Seat",
        "seats": 1,
        "price": Decimal("1499.00"),
        "payment_link": TIRAMISU_PAYMENT_LINK,
        "note": "",
    },
    {
        "name": "2 Seats",
        "seats": 2,
        "price": Decimal("2998.00"),
        "payment_link": "",
        "note": "Paste the 2-seat Razorpay link when you have it.",
    },
    {
        "name": "3 Seats",
        "seats": 3,
        "price": Decimal("4497.00"),
        "payment_link": "",
        "note": "Paste the 3-seat Razorpay link when you have it.",
    },
)


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
                seo_title=HOME_SEO_TITLE,
                search_description=HOME_SEARCH_DESCRIPTION,
                tagline="Learn. Create. Indulge.",
                hero_title="Tiramisu",
                hero_kicker="Making Workshop",
                gold_banner="Eggless tiramisu making",
                workshop_date=FLYER_DATE,
                start_time=FLYER_START,
                end_time=FLYER_END,
                venue=FLYER_VENUE,
                chef_name=FLYER_CHEF,
                price_per_seat=FLYER_PRICE,
            )
            root.add_child(instance=home)
            home.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Published Cafe Orelo home page."))
        else:
            home_changed = False
            if home.intro != FLYER_INTRO:
                home.intro = FLYER_INTRO
                home_changed = True
            if not home.seo_title:
                home.seo_title = HOME_SEO_TITLE
                home_changed = True
            if not home.search_description:
                home.search_description = HOME_SEARCH_DESCRIPTION
                home_changed = True
            if home_changed:
                home.save_revision().publish()
                self.stdout.write(self.style.SUCCESS("Updated home intro/SEO to match the flyer."))
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
        seo_defaults = {
            "seo_title": WORKSHOP_SEO_TITLE,
            "search_description": WORKSHOP_SEARCH_DESCRIPTION,
        }
        if workshop is None:
            workshop = WorkshopPage(
                slug="tiramisu-workshop",
                description="",
                payment_link_url=TIRAMISU_PAYMENT_LINK,
                **flyer_fields,
                **seo_defaults,
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
            if not workshop.payment_link_url:
                workshop.payment_link_url = TIRAMISU_PAYMENT_LINK
                changed = True
            for key, value in seo_defaults.items():
                if not getattr(workshop, key):
                    setattr(workshop, key, value)
                    changed = True
            if changed:
                workshop.save_revision().publish()
                self.stdout.write(self.style.SUCCESS("Updated workshop page to match the flyer."))
            else:
                self.stdout.write("Workshop page already exists.")

        if not workshop.packages.exists():
            for index, data in enumerate(TIRAMISU_PACKAGES):
                WorkshopPackage.objects.create(page=workshop, sort_order=index, **data)
            workshop.save_revision().publish()
            self.stdout.write(self.style.SUCCESS("Seeded tiramisu packages (1 / 2 / 3 seats)."))

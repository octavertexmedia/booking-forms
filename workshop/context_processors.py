from workshop import seo


def public_seo(request):
    return {
        "public_base_url": seo.public_base_url(),
        "seo_site_name": seo.SITE_NAME,
        "seo_og_locale": seo.OG_LOCALE,
        "seo_favicon_url": seo.absolute_static(seo.FAVICON),
        "seo_apple_touch_url": seo.absolute_static(seo.APPLE_TOUCH),
        "seo_og_home_url": seo.absolute_static(seo.OG_HOME),
        "seo_og_default_alt": (
            "Cafe Orelo Tiramisu Making Workshop with Chef Aanchal Wadhwa, "
            "Sunday 23 August 2026, 3–5 PM, ₹1499"
        ),
        "website_json_ld": seo.json_ld_script(seo.graph_payload(*seo.website_json_ld())),
    }
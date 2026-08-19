import os

from django.core.wsgi import get_wsgi_application

_default_settings = (
    "portal.settings.serverless"
    if os.environ.get("VERCEL")
    else "portal.settings.local"
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", _default_settings)

application = get_wsgi_application()


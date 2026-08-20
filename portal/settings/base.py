import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = env(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "unsafe-dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "workshop",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "portal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "workshop" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "workshop.context_processors.public_seo",
            ],
        },
    },
]

WSGI_APPLICATION = "portal.wsgi.application"
ASGI_APPLICATION = "portal.asgi.application"

# Neon pooled URL for request traffic. Fall back to SQLite only when unset.
_database_url = env("DATABASE_URL")
if _database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            _database_url,
            conn_max_age=0,
            ssl_require="sslmode" not in _database_url,
        )
    }
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DATABASE_URL_UNPOOLED = env("DATABASE_URL_UNPOOLED")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "workshop" / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

WAGTAIL_SITE_NAME = "Cafe Orelo Workshops"
WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAILADMIN_BASE_URL = env("WAGTAILADMIN_BASE_URL", "http://127.0.0.1:8000")
WAGTAILDOCS_EXTENSIONS = ["pdf", "docx"]
WAGTAILIMAGES_FEATURE_DETECTION_ENABLED = False
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}

PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET")
# Bookings webhook secret. Prefer the tiramisu-specific name; keep the generic
# name as fallback so older Vercel envs still verify signatures.
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET_TIRAMISU") or env(
    "RAZORPAY_WEBHOOK_SECRET"
)
RAZORPAY_MOCK = env_bool("RAZORPAY_MOCK", False)

WHATSAPP_API_URL = env("WHATSAPP_API_URL")
WHATSAPP_API_TOKEN = env("WHATSAPP_API_TOKEN")
WHATSAPP_EXTRA_PAYLOAD = env("WHATSAPP_EXTRA_PAYLOAD", "{}")

CRON_SECRET = env("CRON_SECRET")

EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "465") or "465")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
# Port 465 = implicit SSL. Port 587 = STARTTLS. Django forbids both True.
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", EMAIL_PORT == 465)
EMAIL_USE_TLS = False if EMAIL_USE_SSL else env_bool("EMAIL_USE_TLS", EMAIL_PORT == 587)
DEFAULT_FROM_EMAIL = (
    env("DEFAULT_FROM_EMAIL")
    or (f"Cafe Orelo <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "")
    or "Cafe Orelo <info@healthyome.in>"
)
# Optional HTTP mail (e.g. Resend) if Vercel blocks outbound SMTP 465.
EMAIL_HTTP_URL = env("EMAIL_HTTP_URL")
EMAIL_HTTP_TOKEN = env("EMAIL_HTTP_TOKEN")
_email_backend = env("EMAIL_BACKEND")
if _email_backend:
    EMAIL_BACKEND = _email_backend
elif EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
elif DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "workshop": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "ap-south-1")
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID") or None
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY") or None
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN")
AWS_S3_DEFAULT_ACL = env("AWS_S3_DEFAULT_ACL", "public-read") or None
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

if AWS_STORAGE_BUCKET_NAME:
    _s3_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": AWS_S3_REGION_NAME,
        "default_acl": AWS_S3_DEFAULT_ACL,
        "querystring_auth": False,
        "file_overwrite": False,
        "object_parameters": AWS_S3_OBJECT_PARAMETERS,
    }
    if AWS_ACCESS_KEY_ID:
        _s3_options["access_key"] = AWS_ACCESS_KEY_ID
    if AWS_SECRET_ACCESS_KEY:
        _s3_options["secret_key"] = AWS_SECRET_ACCESS_KEY
    if AWS_S3_CUSTOM_DOMAIN:
        _s3_options["custom_domain"] = AWS_S3_CUSTOM_DOMAIN

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {**_s3_options, "location": "media"},
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3StaticStorage",
            "OPTIONS": {**_s3_options, "location": "static"},
        },
    }
    MEDIA_URL = (
        f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
        if AWS_S3_CUSTOM_DOMAIN
        else f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/media/"
    )
    STATIC_URL = (
        f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
        if AWS_S3_CUSTOM_DOMAIN
        else f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/"
    )

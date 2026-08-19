from .base import *  # noqa: F403

DEBUG = env_bool("DJANGO_DEBUG", False)  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)  # noqa: F405

# Lambda / Vercel have a read-only filesystem except /tmp.
FILE_UPLOAD_TEMP_DIR = "/tmp"
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Never hold Postgres connections across frozen serverless workers.
if "default" in DATABASES:  # noqa: F405
    DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# WhiteNoise is unused when static files are on S3; keep it harmless if S3 is unset.
WHITENOISE_MANIFEST_STRICT = False

# Vercel injects VERCEL=1 plus the deployment host. SQLite on the app disk is
# not writable there, so fall back to /tmp until Neon URLs are set.
if env("VERCEL"):  # noqa: F405
    _vercel_host = env("VERCEL_PROJECT_PRODUCTION_URL") or env("VERCEL_URL")  # noqa: F405
    if ".vercel.app" not in ALLOWED_HOSTS:  # noqa: F405
        ALLOWED_HOSTS.append(".vercel.app")  # noqa: F405
    if _vercel_host and _vercel_host not in ALLOWED_HOSTS:  # noqa: F405
        ALLOWED_HOSTS.append(_vercel_host)  # noqa: F405
    if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:  # noqa: F405
        CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")  # noqa: F405
    if _vercel_host:
        _origin = f"https://{_vercel_host}"
        if _origin not in CSRF_TRUSTED_ORIGINS:  # noqa: F405
            CSRF_TRUSTED_ORIGINS.append(_origin)  # noqa: F405
        if PUBLIC_BASE_URL in {"", "http://127.0.0.1:8000"}:  # noqa: F405
            PUBLIC_BASE_URL = _origin  # noqa: F405
        if WAGTAILADMIN_BASE_URL in {"", "http://127.0.0.1:8000"}:  # noqa: F405
            WAGTAILADMIN_BASE_URL = _origin  # noqa: F405
    if not env("DATABASE_URL"):  # noqa: F405
        DATABASES["default"] = {  # noqa: F405
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "/tmp/db.sqlite3",
        }

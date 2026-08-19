from .base import *  # noqa: F403

DEBUG = env_bool("DJANGO_DEBUG", True)  # noqa: F405

for _host in ("testserver", ".localhost"):
    if _host not in ALLOWED_HOSTS:  # noqa: F405
        ALLOWED_HOSTS.append(_host)  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

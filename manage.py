#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main() -> None:
    _default_settings = (
        "portal.settings.serverless"
        if os.environ.get("VERCEL")
        else "portal.settings.local"
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", _default_settings)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Activate the virtualenv and install requirements.txt."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

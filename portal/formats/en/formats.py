# Django locale formats plus 12-hour times that Wagtail shows in admin.
DATE_FORMAT = "d M Y"
TIME_FORMAT = "h:i A"
DATETIME_FORMAT = "d M Y, h:i A"
SHORT_DATE_FORMAT = "d M Y"
SHORT_DATETIME_FORMAT = "d M Y, h:i A"
FIRST_DAY_OF_WEEK = 1
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3

DATE_INPUT_FORMATS = [
    "%d %b %Y",  # 23 Aug 2026 — Wagtail date widget
    "%d %B %Y",
    "%d %b, %Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%b %d %Y",
    "%b %d, %Y",
]

TIME_INPUT_FORMATS = [
    "%I:%M %p",  # 03:00 PM — Wagtail time widget
    "%I:%M%p",
    "%I:%M:%S %p",
    "%H:%M",  # 15:00
    "%H:%M:%S",
    "%H:%M:%S.%f",
]

DATETIME_INPUT_FORMATS = [
    "%d %b %Y, %I:%M %p",
    "%d %b %Y %I:%M %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M",
]

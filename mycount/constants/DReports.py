"""Bounds for interactive reports."""

from typing import Final


class DReports:
    DEFAULT_DAYS: Final[int] = 30
    PAGE_SIZE: Final[int] = 50
    PREFERENCES_COOKIE: Final[str] = "mycount_report_filters"
    PREFERENCE_FIELDS: Final[tuple[str, ...]] = ("site", "start", "end", "timezone", "filter")
    TEST_SITE_PREFIX: Final[str] = "mycount_smoke_"
    TEST_PAGE_URL_PATTERN: Final[str] = r"^https?://[^/]+/__mycount_test__(/|$)"

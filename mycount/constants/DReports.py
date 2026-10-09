"""Bounds for interactive reports."""

from typing import Final


class DReports:
    DEFAULT_DAYS: Final[int] = 30
    MAX_DAYS: Final[int] = 366
    PAGE_SIZE: Final[int] = 50
    TEST_SITE_PREFIX: Final[str] = "mycount_smoke_"
    TEST_PAGE_URL_PATTERN: Final[str] = r"^https?://[^/]+/__mycount_test__(/|$)"

"""Evidence thresholds for rotating Windows/Chrome crawl campaigns."""

from typing import Final


class DCrawlCampaigns:
    WINDOW_HOURS: Final[int] = 48
    MIN_IDENTITIES: Final[int] = 12
    MIN_PAGES: Final[int] = 12
    MIN_PAIRS: Final[int] = 6
    MIN_PAIR_SECONDS: Final[int] = 2
    MAX_PAIR_SECONDS: Final[int] = 8
    CADENCE_SESSIONS: Final[int] = 8
    MIN_INTERVAL_SECONDS: Final[int] = 60
    MAX_INTERVAL_SECONDS: Final[int] = 14400
    MAX_INTERVAL_MULTIPLE: Final[int] = 4
    INTERVAL_TOLERANCE: Final[float] = 0.08
    MIN_CADENCE_SHARE: Final[float] = 0.8
    BROWSER: Final[str] = "Chrome"
    OS: Final[str] = "Windows"
    PLATFORM: Final[str] = "Win32"
    VENDOR: Final[str] = "Google Inc."

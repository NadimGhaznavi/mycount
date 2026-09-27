"""Bounds for optional browser-reported analytics fields."""

from typing import Final


class DVisitorDetails:
    BOT_BROWSER_FAMILIES: Final[tuple[str, ...]] = ("Googlebot", "GoogleOther")
    MAX_REFERRER_LENGTH: Final[int] = 4096
    MAX_HOST_LENGTH: Final[int] = 253
    TEXT_LENGTH: Final[int] = 128
    VERSION_LENGTH: Final[int] = 64
    INTEGER_RANGES: Final[dict[str, tuple[int, int]]] = {
        "screen_width": (0, 100000), "screen_height": (0, 100000),
        "available_width": (0, 100000), "available_height": (0, 100000),
        "viewport_width": (0, 100000), "viewport_height": (0, 100000),
        "color_depth": (0, 128), "pixel_depth": (0, 128),
        "timezone_offset": (-1440, 1440), "hardware_concurrency": (0, 65536),
        "max_touch_points": (0, 1024), "connection_rtt": (0, 3600000),
    }
    NUMBER_RANGES: Final[dict[str, tuple[float, float]]] = {
        "pixel_ratio": (0.01, 100), "device_memory": (0, 65536),
        "connection_downlink": (0, 1000000),
    }
    BOOLEAN_FIELDS: Final[frozenset[str]] = frozenset({
        "cookie_enabled", "online", "pdf_viewer_enabled", "webdriver",
        "global_privacy_control", "save_data", "reduced_motion",
    })
    TEXT_FIELDS: Final[frozenset[str]] = frozenset({"timezone", "platform", "vendor"})
    ENUM_FIELDS: Final[dict[str, tuple[str, ...]]] = {
        "color_scheme": ("dark", "light", "no-preference"),
        "connection_effective_type": ("slow-2g", "2g", "3g", "4g"),
        "navigation_type": ("navigate", "reload", "back_forward", "prerender"),
        "do_not_track": ("0", "1", "yes", "no", "unspecified"),
    }

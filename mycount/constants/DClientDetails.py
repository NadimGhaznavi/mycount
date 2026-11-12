"""Mapping from browser detail keys to nullable page-view columns."""

from typing import Final


class DClientDetails:
    BATCH_SIZE: Final[int] = 500
    # Payload key, database column, SQL type. Browser and GeoIP timezones differ.
    COLUMNS: Final[tuple[tuple[str, str, str], ...]] = (
        ("screen_width", "screen_width", "INT UNSIGNED"),
        ("screen_height", "screen_height", "INT UNSIGNED"),
        ("available_width", "available_width", "INT UNSIGNED"),
        ("available_height", "available_height", "INT UNSIGNED"),
        ("color_depth", "color_depth", "TINYINT UNSIGNED"),
        ("pixel_depth", "pixel_depth", "TINYINT UNSIGNED"),
        ("viewport_width", "viewport_width", "INT UNSIGNED"),
        ("viewport_height", "viewport_height", "INT UNSIGNED"),
        ("pixel_ratio", "pixel_ratio", "DOUBLE"),
        ("timezone", "browser_timezone", "VARCHAR(128)"),
        ("timezone_offset", "timezone_offset", "SMALLINT"),
        ("platform", "platform", "VARCHAR(128)"),
        ("vendor", "vendor", "VARCHAR(128)"),
        ("cookie_enabled", "cookie_enabled", "BOOLEAN"),
        ("online", "online", "BOOLEAN"),
        ("pdf_viewer_enabled", "pdf_viewer_enabled", "BOOLEAN"),
        ("hardware_concurrency", "hardware_concurrency", "INT UNSIGNED"),
        ("device_memory", "device_memory", "DOUBLE"),
        ("max_touch_points", "max_touch_points", "SMALLINT UNSIGNED"),
        ("webdriver", "webdriver", "BOOLEAN"),
        ("color_scheme", "color_scheme", "VARCHAR(16)"),
        ("reduced_motion", "reduced_motion", "BOOLEAN"),
        ("connection_effective_type", "connection_effective_type", "VARCHAR(16)"),
        ("connection_downlink", "connection_downlink", "DOUBLE"),
        ("connection_rtt", "connection_rtt", "INT UNSIGNED"),
        ("save_data", "save_data", "BOOLEAN"),
        ("navigation_type", "navigation_type", "VARCHAR(16)"),
        ("do_not_track", "do_not_track", "VARCHAR(16)"),
        ("global_privacy_control", "global_privacy_control", "BOOLEAN"),
    )

"""Columns displayed and filtered in the visitor record table."""

from typing import Final

from mycount.constants.DVisitorDetails import DVisitorDetails


class DVisitors:
    PAGE_SIZE: Final[int] = 30
    NUMERIC_COLUMNS: Final[frozenset[str]] = frozenset(
        DVisitorDetails.INTEGER_RANGES.keys() | DVisitorDetails.NUMBER_RANGES.keys()
        | DVisitorDetails.BOOLEAN_FIELDS | {"is_bot", "latitude", "longitude"}
    )
    COLUMNS: Final[tuple[tuple[str, str], ...]] = (
        ("received_at", "Received at (UTC)"),
        ("site", "Site"),
        ("url", "URL"),
        ("country_name", "Country"),
        ("region_name", "Region"),
        ("city_name", "City"),
        ("languages", "Languages"),
        ("page_view_id", "Page view ID"),
        ("page_id", "Page ID"),
        ("country_code", "Country code"),
        ("browser_family", "Browser"),
        ("browser_version", "Browser version"),
        ("os_family", "Operating system"),
        ("os_version", "Operating system version"),
        ("device_category", "Device category"),
        ("device_brand", "Device brand"),
        ("device_model", "Device model"),
        ("is_bot", "Is bot"),
        ("referrer_host", "Referrer host"),
        ("referrer", "Referrer"),
        ("search", "Query string"),
        ("user_agent", "User agent"),
        ("visitor_id", "Visitor ID"),
        ("ip_address", "IP address"),
        ("latitude", "Latitude"),
        ("longitude", "Longitude"),
        ("zip", "Postal code"),
        ("timezone", "GeoIP time zone"),
        ("screen_width", "Screen width"),
        ("screen_height", "Screen height"),
        ("available_width", "Available width"),
        ("available_height", "Available height"),
        ("color_depth", "Color depth"),
        ("pixel_depth", "Pixel depth"),
        ("viewport_width", "Viewport width"),
        ("viewport_height", "Viewport height"),
        ("pixel_ratio", "Pixel ratio"),
        ("browser_timezone", "Browser time zone"),
        ("timezone_offset", "Time zone offset (minutes)"),
        ("platform", "Platform"),
        ("vendor", "Vendor"),
        ("cookie_enabled", "Cookies enabled"),
        ("online", "Online"),
        ("pdf_viewer_enabled", "PDF viewer enabled"),
        ("hardware_concurrency", "Logical processors"),
        ("device_memory", "Device memory (GB)"),
        ("max_touch_points", "Maximum touch points"),
        ("webdriver", "Webdriver"),
        ("color_scheme", "Color scheme"),
        ("reduced_motion", "Reduced motion"),
        ("connection_effective_type", "Connection type"),
        ("connection_downlink", "Downlink (Mbps)"),
        ("connection_rtt", "Round-trip time (ms)"),
        ("save_data", "Save data"),
        ("navigation_type", "Navigation type"),
        ("do_not_track", "Do Not Track"),
        ("global_privacy_control", "Global Privacy Control"),
    )

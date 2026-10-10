"""Columns displayed and filtered in the visitor record table."""

from typing import Final


class DVisitors:
    COLUMNS: Final[tuple[tuple[str, str], ...]] = (
        ("received_at", "Received at (UTC)"),
        ("site", "Site"),
        ("url", "URL"),
        ("country_name", "Country"),
        ("region_name", "Region"),
        ("city_name", "City"),
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
        ("timezone", "Time zone"),
        ("client_details", "Client details"),
    )

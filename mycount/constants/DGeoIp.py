"""BMGeoIP service and location storage limits."""

from typing import Final


class DGeoIp:
    HOST: Final[str] = "geoip.osoyalce.com"
    PORT: Final[int] = 54300
    TIMEOUT: Final[int] = 5
    COLUMNS: Final[tuple[str, ...]] = (
        "ip_version", "start_ip", "end_ip", "continent", "country_code", "country",
        "state", "city", "zip", "timezone", "latitude", "longitude", "accuracy", "source",
    )
    COUNTRY_NAME_LENGTH: Final[int] = 128
    ZIP_LENGTH: Final[int] = 128
    TIMEZONE_LENGTH: Final[int] = 128
    REGION_NAME_LENGTH: Final[int] = 128
    # Retained only to remove the schedule from former local-dataset installations.
    CRON_FILE: Final[str] = "/etc/cron.d/mycount-geoip"

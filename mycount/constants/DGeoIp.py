"""Public reference-data source and refresh settings."""

from typing import Final


class DGeoIp:
    URL: Final[str] = "https://raw.githubusercontent.com/ipapi-is/ipapi/main/databases/geolocationDatabaseIPv{version}.csv.zip"
    MEMBER: Final[str] = "geolocationDatabaseIPv{version}.csv"
    VERSIONS: Final[tuple[int, ...]] = (4, 6)
    COLUMNS: Final[tuple[str, ...]] = (
        "ip_version", "start_ip", "end_ip", "continent", "country_code", "country",
        "state", "city", "zip", "timezone", "latitude", "longitude", "accuracy", "source",
    )
    DOWNLOAD_TIMEOUT: Final[int] = 120
    BATCH_SIZE: Final[int] = 1000
    ZIP_LENGTH: Final[int] = 128
    TIMEZONE_LENGTH: Final[int] = 128
    CONTINENT_LENGTH: Final[int] = 64
    REGION_NAME_LENGTH: Final[int] = 128
    CRON_FILE: Final[str] = "/etc/cron.d/mycount-geoip"
    CRON_SCHEDULE: Final[str] = "17 3 * * 0"
    LOCK_NAME: Final[str] = "mycount:geoip-refresh"

"""GeoNames city reference data and refresh scheduling."""

from typing import Final


class DCities:
    DIRECTORY: Final[str] = "data/cities"
    CRON_FILE: Final[str] = "/etc/cron.d/mycount-cities"
    DEFAULT_SCHEDULE: Final[str] = "0 3 1 */3 *"
    SOURCE: Final[str] = "https://download.geonames.org/export/dump/"
    TIMEOUT: Final[int] = 60
    MAX_DOWNLOAD_BYTES: Final[int] = 64 * 1024 * 1024
    MAX_EXTRACT_BYTES: Final[int] = 256 * 1024 * 1024


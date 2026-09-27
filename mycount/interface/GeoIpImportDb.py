"""Stage reference ranges and publish a complete refresh atomically."""

from contextlib import contextmanager
from collections.abc import Iterator, Sequence

from mycount.constants.DGeoIp import DGeoIp
from mycount.entity.GeoIpRange import GeoIpRange
from mycount.interface.DbMgr import DbMgr


class GeoIpImportDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    @contextmanager
    def refresh(self) -> Iterator[None]:
        acquired = self._db.query("SELECT GET_LOCK(%s, 0) AS acquired", (DGeoIp.LOCK_NAME,))[0]["acquired"]
        if acquired != 1:
            raise RuntimeError("A GeoIP refresh is already running.")
        try:
            self._db.execute("DROP TABLE IF EXISTS geoip_ranges_next")
            self._db.execute("CREATE TABLE geoip_ranges_next LIKE geoip_ranges")
            yield
            self._db.execute("DROP TABLE IF EXISTS geoip_ranges_previous")
            self._db.execute("RENAME TABLE geoip_ranges TO geoip_ranges_previous, geoip_ranges_next TO geoip_ranges")
            self._db.execute("DROP TABLE geoip_ranges_previous")
        finally:
            try:
                self._db.execute("DROP TABLE IF EXISTS geoip_ranges_next")
            finally:
                self._db.query("SELECT RELEASE_LOCK(%s)", (DGeoIp.LOCK_NAME,))

    def append(self, ranges: Sequence[GeoIpRange]) -> None:
        self._db.execute_many("""
            INSERT INTO geoip_ranges_next
                (ip_version, start_ip, end_ip, country_code, region_name, city_name,
                 continent, latitude, longitude, zip, timezone)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [
            (item.version, item.start, item.end, item.location.country_code,
             item.location.region_name, item.location.city_name, item.location.continent,
             item.location.latitude, item.location.longitude, item.location.zip, item.location.timezone) for item in ranges
        ])

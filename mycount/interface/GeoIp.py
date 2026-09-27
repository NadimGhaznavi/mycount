"""Look up public reference ranges through the shared MariaDB bridge."""

from ipaddress import ip_address

from mycount.entity.GeoLocation import GeoLocation
from mycount.interface.DbMgr import DbMgr


class GeoIp:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def locate(self, address: str) -> GeoLocation:
        ip = ip_address(address)
        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            return GeoLocation()
        key = int(ip).to_bytes(16, "big")
        # Both bounds matter: the source includes nested IPv6 ranges.
        rows = self._db.query("""
            SELECT continent, country_code, region_name, city_name, latitude, longitude, zip, timezone FROM geoip_ranges
            WHERE ip_version = %s AND start_ip <= %s AND end_ip >= %s
            ORDER BY start_ip DESC, end_ip ASC LIMIT 1
        """, (ip.version, key, key))
        if not rows:
            return GeoLocation()
        row = rows[0]
        return GeoLocation(continent=row["continent"], country_code=row["country_code"],
                           region_name=row["region_name"], city_name=row["city_name"],
                           latitude=row["latitude"], longitude=row["longitude"],
                           zip=row["zip"], timezone=row["timezone"])

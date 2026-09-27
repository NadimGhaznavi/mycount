"""Explicit schema for public geolocation reference data."""

from mycount.interface.DbMgr import DbMgr
from mycount.interface.CountryNameMigration import CountryNameMigration
from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount


class GeoIpSchema:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS geoip_ranges (
                ip_version TINYINT UNSIGNED NOT NULL,
                start_ip BINARY(16) NOT NULL,
                end_ip BINARY(16) NOT NULL,
                country_code CHAR(2) CHARACTER SET ascii COLLATE ascii_bin NULL,
                region_name VARCHAR({DGeoIp.REGION_NAME_LENGTH}) NULL,
                city_name VARCHAR({DMyCount.CITY_NAME_LENGTH}) NULL,
                PRIMARY KEY (ip_version, start_ip, end_ip),
                INDEX idx_geoip_lookup (ip_version, start_ip DESC, end_ip),
                CHECK (ip_version IN (4, 6)),
                CHECK (start_ip <= end_ip)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
        """)
        self._db.execute(f"""
            ALTER TABLE geoip_ranges
                ADD COLUMN IF NOT EXISTS country_name VARCHAR({DGeoIp.COUNTRY_NAME_LENGTH}) NULL,
                DROP COLUMN IF EXISTS continent,
                ADD COLUMN IF NOT EXISTS latitude DOUBLE NULL,
                ADD COLUMN IF NOT EXISTS longitude DOUBLE NULL,
                ADD COLUMN IF NOT EXISTS zip VARCHAR({DGeoIp.ZIP_LENGTH}) NULL,
                ADD COLUMN IF NOT EXISTS timezone VARCHAR({DGeoIp.TIMEZONE_LENGTH}) NULL
        """)
        CountryNameMigration(self._db).apply("geoip_ranges")

"""Explicit visitor schema setup for installation and upgrades."""

from mycount.interface.DbMgr import DbMgr
from mycount.interface.CountryNameMigration import CountryNameMigration
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DVisitorDetails import DVisitorDetails


class VisitorSchema:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        """Create missing tables without replacing existing records.

        Run outside an application transaction: MariaDB DDL commits implicitly.
        Future schema changes require explicit migrations here.
        """
        # Hash the complete URL for indexing; retain its exact spelling for reporting.
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                page_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                site VARCHAR(100) NOT NULL,
                url TEXT NOT NULL,
                url_hash BINARY(32) GENERATED ALWAYS AS (UNHEX(SHA2(url, 256))) STORED,
                UNIQUE KEY uq_page_site_url (site, url_hash)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
        """)
        self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS page_views (
                page_view_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                page_id BIGINT UNSIGNED NOT NULL,
                received_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                country_code CHAR(2) CHARACTER SET ascii COLLATE ascii_bin NULL,
                region_name VARCHAR(128) NULL,
                city_name VARCHAR({DMyCount.CITY_NAME_LENGTH}) NULL,
                browser_family VARCHAR(64) NULL,
                os_family VARCHAR(64) NULL,
                device_category VARCHAR(16) NULL,
                CONSTRAINT ck_device_category CHECK (
                    device_category IN ('desktop', 'mobile', 'tablet', 'other')
                ),
                INDEX idx_view_time (received_at, page_view_id),
                INDEX idx_view_page_time (page_id, received_at),
                CONSTRAINT fk_view_page FOREIGN KEY (page_id) REFERENCES pages(page_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
        """)
        self._db.execute("ALTER TABLE page_views DROP COLUMN IF EXISTS region_code")
        # Nullable additions preserve historical rows and support cached older clients.
        self._db.execute(f"""
            ALTER TABLE page_views
                ADD COLUMN IF NOT EXISTS referrer_host VARCHAR({DVisitorDetails.MAX_HOST_LENGTH}) NULL,
                ADD COLUMN IF NOT EXISTS user_agent TEXT NULL,
                ADD COLUMN IF NOT EXISTS browser_version VARCHAR({DVisitorDetails.VERSION_LENGTH}) NULL,
                ADD COLUMN IF NOT EXISTS os_version VARCHAR({DVisitorDetails.VERSION_LENGTH}) NULL,
                ADD COLUMN IF NOT EXISTS device_brand VARCHAR({DVisitorDetails.TEXT_LENGTH}) NULL,
                ADD COLUMN IF NOT EXISTS device_model VARCHAR({DVisitorDetails.TEXT_LENGTH}) NULL,
                ADD COLUMN IF NOT EXISTS is_bot BOOLEAN NULL,
                ADD COLUMN IF NOT EXISTS client_details JSON NULL
        """)
        self._db.execute("""
            ALTER TABLE page_views
                ADD COLUMN IF NOT EXISTS visitor_id BINARY(16) NULL,
                ADD INDEX IF NOT EXISTS idx_view_visitor_time (visitor_id, received_at)
        """)
        self._db.execute("""
            ALTER TABLE page_views
                ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45)
                    CHARACTER SET ascii COLLATE ascii_bin NULL
        """)
        self._db.execute(f"""
            ALTER TABLE page_views
                ADD COLUMN IF NOT EXISTS search TEXT NULL,
                ADD COLUMN IF NOT EXISTS referrer TEXT NULL,
                ADD COLUMN IF NOT EXISTS country_name VARCHAR({DGeoIp.COUNTRY_NAME_LENGTH}) NULL,
                DROP COLUMN IF EXISTS continent,
                ADD COLUMN IF NOT EXISTS latitude DOUBLE NULL,
                ADD COLUMN IF NOT EXISTS longitude DOUBLE NULL,
                ADD COLUMN IF NOT EXISTS zip VARCHAR({DGeoIp.ZIP_LENGTH}) NULL,
                ADD COLUMN IF NOT EXISTS timezone VARCHAR({DGeoIp.TIMEZONE_LENGTH}) NULL
        """)
        width = self._db.query("""
            SELECT CHARACTER_MAXIMUM_LENGTH AS width FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'page_views' AND COLUMN_NAME = 'city_name'
        """)[0]["width"]
        if width < DMyCount.CITY_NAME_LENGTH:
            self._db.execute(f"ALTER TABLE page_views MODIFY city_name VARCHAR({DMyCount.CITY_NAME_LENGTH}) NULL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS page_view_languages (
                page_view_id BIGINT UNSIGNED NOT NULL,
                preference_order SMALLINT UNSIGNED NOT NULL,
                language_tag VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                PRIMARY KEY (page_view_id, preference_order),
                CONSTRAINT ck_language_order CHECK (preference_order > 0),
                CONSTRAINT fk_language_view FOREIGN KEY (page_view_id)
                    REFERENCES page_views(page_view_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
        """)
        CountryNameMigration(self._db).apply("page_views")


if __name__ == "__main__":
    db = DbMgr()
    try:
        VisitorSchema(db).apply()
    finally:
        db.close()

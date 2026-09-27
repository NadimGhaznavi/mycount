"""Backfill missing country names from existing ISO country codes."""

from typing import Literal

import pycountry

from mycount.interface.DbMgr import DbMgr


class CountryNameMigration:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self, table: Literal["geoip_ranges", "page_views"]) -> None:
        with self._db.transaction():
            codes = self._db.query(f"""
                SELECT DISTINCT country_code FROM {table}
                WHERE country_name IS NULL AND country_code IS NOT NULL
            """)
            for row in codes:
                country = pycountry.countries.get(alpha_2=row["country_code"].upper())
                if country is not None:
                    self._db.execute(f"""
                        UPDATE {table} SET country_name = %s
                        WHERE country_code = %s AND country_name IS NULL
                    """, (country.name, row["country_code"]))

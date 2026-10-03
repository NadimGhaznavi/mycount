"""Backfill country names in bounded, independently committed primary-key batches."""

import logging
from time import monotonic

import pycountry

from mycount.constants.DCountryNameMigration import DCountryNameMigration
from mycount.interface.DbMgr import DbMgr


class CountryNameMigration:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        table = "page_views"
        keys = ("page_view_id",)
        columns = ", ".join(keys)
        after = ""
        parameters = ()
        scanned = updated = 0
        last_report = monotonic()
        logger = logging.getLogger(__name__)
        logger.info("Backfilling country names in %s", table)
        while True:
            # Read all rows in each key range, including unknown/already-named rows.
            # Filtering for missing names here could scan an unbounded range.
            rows = self._db.query(f"""
                SELECT {columns}, country_code, country_name FROM {table}
                {after} ORDER BY {columns} LIMIT %s
            """, (*parameters, DCountryNameMigration.BATCH_SIZE))
            if not rows:
                break
            names = {}
            pending = []
            for row in rows:
                if row["country_name"] is not None or not row["country_code"]:
                    continue
                code = row["country_code"].upper()
                country = pycountry.countries.get(alpha_2=code)
                if country is not None:
                    names[code] = country.name
                    pending.append(tuple(row[key] for key in keys))
            if pending:
                cases = " ".join("WHEN %s THEN %s" for _ in names)
                key_slots = "(" + ", ".join("%s" for _ in keys) + ")"
                matches = ", ".join(key_slots for _ in pending)
                values = tuple(value for item in names.items() for value in item)
                values += tuple(value for key in pending for value in key)
                with self._db.transaction():
                    updated += self._db.execute(f"""
                        UPDATE {table}
                        SET country_name = CASE UPPER(country_code) {cases} ELSE country_name END
                        WHERE ({columns}) IN ({matches}) AND country_name IS NULL
                    """, values)
            scanned += len(rows)
            if monotonic() - last_report >= 10:
                logger.info("Country names in %s: scanned %d rows, updated %d", table, scanned, updated)
                last_report = monotonic()
            # Seek the next batch by visitor primary key.
            clauses = []
            parameters = ()
            for index, key in enumerate(keys):
                equals = [f"{previous} = %s" for previous in keys[:index]]
                clauses.append("(" + " AND ".join([*equals, f"{key} > %s"]) + ")")
                parameters += tuple(rows[-1][part] for part in keys[:index + 1])
            after = "WHERE " + " OR ".join(clauses)
        logger.info("Country name backfill complete for %s: %d updated", table, updated)

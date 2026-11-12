"""Replace legacy browser JSON with verified, typed page-view columns."""

import json
import logging

from mycount.constants.DClientDetails import DClientDetails
from mycount.interface.DbMgr import DbMgr
from mycount.interface.VisitorDetails import VisitorDetails


class ClientDetailsMigration:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        """Run with application services stopped, outside a caller transaction.

        DDL commits implicitly. Each backfill batch commits only after its stored
        values are verified; failures retain the JSON so the upgrade can resume.
        """
        additions = ", ".join(
            f"ADD COLUMN IF NOT EXISTS {column} {sql_type} NULL DEFAULT NULL"
            for _, column, sql_type in DClientDetails.COLUMNS
        )
        self._db.execute(f"ALTER TABLE page_views {additions}")
        if not self._db.query("""
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'page_views'
                AND COLUMN_NAME = 'client_details'
        """):
            return

        logger = logging.getLogger(__name__)
        logger.info("Migrating client details from JSON to page-view columns")
        columns = tuple(column for _, column, _ in DClientDetails.COLUMNS)
        assignments = ", ".join(f"{column} = %s" for column in columns)
        after = migrated = 0
        while True:
            rows = self._db.query("""
                SELECT page_view_id, client_details FROM page_views
                WHERE page_view_id > %s ORDER BY page_view_id LIMIT %s
            """, (after, DClientDetails.BATCH_SIZE))
            if not rows:
                break
            values = []
            for row in rows:
                try:
                    source = json.loads(row["client_details"]) if row["client_details"] is not None else {}
                    details = dict(VisitorDetails.resolve(source))
                except ValueError as error:
                    raise ValueError(
                        f"Invalid legacy client details for page_view_id {row['page_view_id']}."
                    ) from error
                values.append(tuple(details.get(key) for key, _, _ in DClientDetails.COLUMNS)
                              + (row["page_view_id"],))
            last = rows[-1]["page_view_id"]
            with self._db.transaction():
                self._db.execute_many(
                    f"UPDATE page_views SET {assignments} WHERE page_view_id = %s", values,
                )
                stored = self._db.query(f"""
                    SELECT {', '.join(columns)}, page_view_id FROM page_views
                    WHERE page_view_id > %s AND page_view_id <= %s ORDER BY page_view_id
                """, (after, last))
                actual = [tuple(row[column] for column in columns) + (row["page_view_id"],)
                          for row in stored]
                if actual != values:
                    raise ValueError(
                        f"Client details verification failed for page_view_ids {after + 1}–{last}."
                    )
            after = last
            migrated += len(rows)
            logger.debug("Verified client details for %d page views", migrated)

        self._db.execute("ALTER TABLE page_views DROP COLUMN client_details")
        logger.info("Client details migration complete: %d page views verified", migrated)

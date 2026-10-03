"""Explicit marketing event schema setup for installation and upgrades."""

from mycount.constants.DMarketing import DMarketing
from mycount.interface.DbMgr import DbMgr


class MarketingSchema:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS marketing_posts (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                posted_at DATETIME NOT NULL,
                platform VARCHAR(32) NOT NULL,
                url VARCHAR({DMarketing.MAX_URL_LENGTH}) NOT NULL,
                notes TEXT NOT NULL,
                created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                INDEX idx_marketing_post_time (posted_at, id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
        """)

"""Store and retrieve marketing events using the shared database interface."""

from datetime import timezone

from mycount.entity.MarketingPost import MarketingPost
from mycount.interface.DbMgr import DbMgr


class MarketingDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def record(self, post: MarketingPost) -> int:
        with self._db.transaction():
            return self._db.insert("""
                INSERT INTO marketing_posts (posted_at, platform, url, notes)
                VALUES (%s, %s, %s, %s)
            """, (post.posted_at.astimezone(timezone.utc).replace(tzinfo=None),
                  post.platform, post.url, post.notes))

    def posts(self) -> list[dict[str, object]]:
        return self._db.query("""
            SELECT id, posted_at, platform, url, notes, created_at
            FROM marketing_posts ORDER BY posted_at DESC, id DESC
        """)

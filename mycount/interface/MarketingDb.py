"""Store and retrieve marketing events using the shared database interface."""

from datetime import datetime, timezone

from mycount.entity.MarketingPost import MarketingPost
from mycount.interface.DbMgr import DbMgr


class MarketingDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def record(self, post: MarketingPost) -> int:
        with self._db.transaction():
            return self._db.insert("""
                INSERT INTO marketing_posts (posted_at, platform, url, notes, screenshot_path, submission_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
            """, (post.posted_at.astimezone(timezone.utc).replace(tzinfo=None),
                  post.platform, post.url, post.notes, post.screenshot_path, post.submission_id))

    def submission(self, submission_id: str) -> int | None:
        rows = self._db.query("SELECT id FROM marketing_posts WHERE submission_id = %s", (submission_id,))
        return rows[0]["id"] if rows else None

    def screenshot_referenced(self, reference: str) -> bool:
        return bool(self._db.query("SELECT id FROM marketing_posts WHERE screenshot_path = %s LIMIT 1", (reference,)))

    def posts(self, *, start: datetime | None = None, end: datetime | None = None) -> list[dict[str, object]]:
        clauses, parameters = [], ()
        if start is not None:
            clauses.append("posted_at >= %s")
            parameters += (start,)
        if end is not None:
            clauses.append("posted_at < %s")
            parameters += (end,)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        return self._db.query(f"""
            SELECT id, posted_at, platform, url, notes, created_at, screenshot_path
            FROM marketing_posts {where} ORDER BY posted_at DESC, id DESC
        """, parameters)

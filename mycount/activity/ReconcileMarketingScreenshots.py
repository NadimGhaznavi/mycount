"""Remove old, unreferenced marketing screenshots while the control service is stopped."""

from datetime import datetime, timedelta, timezone

from mycount.interface.DbMgr import DbMgr
from mycount.interface.MarketingDb import MarketingDb
from mycount.interface.MarketingScreenshots import MarketingScreenshots


class ReconcileMarketingScreenshots:
    def __init__(self, posts: MarketingDb, screenshots: MarketingScreenshots) -> None:
        self._posts = posts
        self._screenshots = screenshots

    def run(self) -> int:
        removed = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        for reference in self._screenshots.older_than(cutoff):
            if not self._posts.screenshot_referenced(reference):
                self._screenshots.remove(reference)
                removed += 1
        return removed


if __name__ == "__main__":
    db = DbMgr()
    try:
        removed = ReconcileMarketingScreenshots(MarketingDb(db), MarketingScreenshots()).run()
        print(f"Removed {removed} unreferenced screenshots older than one day.")
    finally:
        db.close()

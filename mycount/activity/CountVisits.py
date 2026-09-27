"""Read the public site counter using the shared database interface."""

from mycount.interface.DbMgr import DbMgr
from mycount.interface.VisitDb import VisitDb


class CountVisits:
    def count(self, site: str) -> int:
        db = DbMgr()
        try:
            return VisitDb(db).count_by_site(site)
        finally:
            db.close()

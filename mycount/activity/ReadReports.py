"""Own report query selection, snapshot transactions, and connection lifetime."""

from datetime import datetime

from mycount.constants.DReports import DReports
from mycount.entity.Report import Report
from mycount.entity.ReportOptions import ReportOptions
from mycount.interface.DbMgr import DbMgr
from mycount.interface.MarketingDb import MarketingDb
from mycount.interface.VisitDb import VisitDb


class ReadReports:
    def metrics(self, options: ReportOptions) -> Report:
        days = options.day_ranges()
        filters = dict(exclude_bots=options.exclude_bots, start=days[0][1], end=days[-1][2])
        db = DbMgr()
        try:
            with db.transaction(read_only=True):
                visits = VisitDb(db)
                sites = visits.totals_by_site(**filters)
                pages = visits.totals_by_page(**filters)
                locations = visits.totals_by_location(**filters)
                recent = visits.recent_visits(**filters, before=options.before, limit=DReports.PAGE_SIZE + 1)
                referrers = visits.totals_by_referrer(**filters)
                languages = visits.totals_by_language(**filters)
                daily = visits.daily_totals(days, exclude_bots=options.exclude_bots)
                first = visits.first_visit_at()
            older = None
            if len(recent) > DReports.PAGE_SIZE:
                recent = recent[:DReports.PAGE_SIZE]
                older = (recent[-1]["received_at"], recent[-1]["page_view_id"])
            return Report(options, daily, first, sites=sites, pages=pages, locations=locations,
                          recent=recent, referrers=referrers, languages=languages, older=older)
        finally:
            db.close()

    def visitor_map(self, options: ReportOptions) -> Report:
        days = options.day_ranges()
        db = DbMgr()
        try:
            with db.transaction(read_only=True):
                visits = VisitDb(db)
                locations = visits.totals_by_coordinates(
                    exclude_bots=options.exclude_bots, start=days[0][1], end=days[-1][2])
                first = visits.first_visit_at()
            return Report(options, [], first, locations=locations)
        finally:
            db.close()

    def marketing(self, options: ReportOptions) -> Report:
        days = options.day_ranges()
        db = DbMgr()
        try:
            with db.transaction(read_only=True):
                posts = MarketingDb(db).posts(start=days[0][1], end=days[-1][2])
                visits = VisitDb(db)
                daily = visits.daily_totals(days, exclude_bots=options.exclude_bots)
                first = visits.first_visit_at()
            return Report(options, daily, first, posts=posts)
        finally:
            db.close()

    def first_visit_at(self) -> datetime | None:
        db = DbMgr()
        try:
            return VisitDb(db).first_visit_at()
        finally:
            db.close()

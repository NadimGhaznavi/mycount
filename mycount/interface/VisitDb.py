"""Persist a processed visit through the shared database bridge."""

from datetime import datetime, timezone
import json

from mycount.entity.Visit import Visit
from mycount.constants.DVisitorDetails import DVisitorDetails
from mycount.interface.DbMgr import DbMgr
from mycount.constants.DReports import DReports
from mycount.constants.DVisitors import DVisitors
from mycount.constants.DCrawlCampaigns import DCrawlCampaigns
from mycount.entity.CampaignVisit import CampaignVisit


class VisitDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def campaign_candidates(self, site: str, *, start: datetime | None = None,
                            end: datetime | None = None) -> list[CampaignVisit]:
        """Read one site's Windows/Chrome sessions, including earlier classifications.

        These are evidence candidates, not bot decisions. Missing identity or browser
        metadata cannot establish the rotating identity pattern.
        """
        where, params = self._filter(False, start, None, site)
        if end is not None:
            where += " AND v.received_at <= %s"
            params += (end,)
        where += """ AND v.visitor_id IS NOT NULL AND v.ip_address IS NOT NULL
            AND v.browser_family = %s AND v.os_family = %s
            AND JSON_VALUE(v.client_details, '$.platform') = %s
            AND JSON_VALUE(v.client_details, '$.vendor') = %s"""
        params += (DCrawlCampaigns.BROWSER, DCrawlCampaigns.OS,
                   DCrawlCampaigns.PLATFORM, DCrawlCampaigns.VENDOR)
        rows = self._db.query(f"""
            SELECT v.page_view_id, p.site, p.url, v.received_at,
                   v.visitor_id, v.ip_address, v.referrer_host
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where} ORDER BY v.received_at, v.page_view_id
        """, params)
        return [CampaignVisit(**row) for row in rows]

    def mark_campaign_bots(self, ids: tuple[int, ...]) -> int:
        """Classify the reviewed rows atomically without deleting their evidence."""
        if not ids:
            return 0
        placeholders = ", ".join("%s" for _ in ids)
        with self._db.transaction():
            return self._db.execute(
                f"UPDATE page_views SET is_bot = 1 WHERE page_view_id IN ({placeholders}) "
                "AND COALESCE(is_bot, 0) <> 1", ids)

    def record(self, visit: Visit) -> int:
        """Commit the page, view, and language preferences together."""
        with self._db.transaction():
            page_id = self._db.insert(
                "INSERT INTO pages(site, url) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE page_id = LAST_INSERT_ID(page_id)",
                (visit.site, visit.url),
            )
            view_id = self._db.insert("""
                INSERT INTO page_views
                    (page_id, received_at, country_code, region_name,
                     city_name, browser_family, os_family, device_category,
                     search, referrer, referrer_host, user_agent,
                     browser_version, os_version, device_brand, device_model, is_bot, client_details,
                     visitor_id, ip_address, latitude, longitude, zip, timezone, country_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                page_id, visit.received_at.astimezone(timezone.utc).replace(tzinfo=None),
                visit.country_code, visit.region_name, visit.city_name,
                visit.browser_family, visit.os_family, visit.device_category,
                visit.search, visit.referrer,
                visit.referrer_host, visit.user_agent, visit.browser_version, visit.os_version,
                visit.device_brand, visit.device_model, visit.is_bot,
                json.dumps(dict(visit.client_details), allow_nan=False) if visit.client_details else None,
                visit.visitor_id, visit.ip_address, visit.latitude, visit.longitude, visit.zip, visit.timezone, visit.country_name,
            ))
            for position, language in enumerate(visit.languages, start=1):
                self._db.execute(
                    "INSERT INTO page_view_languages "
                    "(page_view_id, preference_order, language_tag) VALUES (%s, %s, %s)",
                    (view_id, position, language),
                )
        return view_id

    def totals_by_page(self, *, exclude_bots: bool = False,
                       start: datetime | None = None, end: datetime | None = None,
                       site: str = "*") -> list[dict[str, object]]:
        """Rank visited pages within each site by views, breaking ties by URL."""
        where, params = self._filter(exclude_bots, start, end, site)
        return self._db.query(f"""
            SELECT p.site, p.url, COUNT(*) AS page_views,
                   MAX(v.received_at) AS last_visited
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            GROUP BY p.page_id, p.site, p.url
            ORDER BY p.site, page_views DESC, p.url
        """, params)

    def totals_by_site(self, *, exclude_bots: bool = False,
                       start: datetime | None = None, end: datetime | None = None,
                       site: str = "*") -> list[dict[str, object]]:
        """Count recorded browser IDs separately from views with no identifier.

        IDs are scoped to each site. Browser counts include automated clients;
        known bot views are reported separately, not treated as people.
        """
        where, params = self._filter(exclude_bots, start, end, site)
        bot_condition, bot_params = self._bot_condition()
        return self._db.query(f"""
            SELECT p.site, COUNT(*) AS page_views, MAX(v.received_at) AS last_visited,
                   COUNT(DISTINCT v.visitor_id) AS unique_browsers,
                   COUNT(CASE WHEN v.visitor_id IS NULL THEN 1 END) AS unidentified_views,
                   COUNT(CASE WHEN {bot_condition} THEN 1 END) AS known_bot_views
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            GROUP BY p.site
            ORDER BY page_views DESC, p.site
        """, (*bot_params, *params))

    def totals_by_location(self, *, exclude_bots: bool = False,
                       start: datetime | None = None, end: datetime | None = None,
                       site: str = "*") -> list[dict[str, object]]:
        """Rank all recorded views by country, state/province, and city."""
        where, params = self._filter(exclude_bots, start, end, site)
        return self._db.query(f"""
            SELECT NULLIF(country_code, '') AS country_code,
                   MAX(NULLIF(country_name, '')) AS country_name,
                   NULLIF(region_name, '') AS region_name,
                   NULLIF(city_name, '') AS city_name, COUNT(*) AS page_views
            FROM page_views v
            {where}
            GROUP BY NULLIF(country_code, ''),
                     NULLIF(region_name, ''), NULLIF(city_name, '')
            ORDER BY page_views DESC, country_name, country_code, region_name, city_name
        """, params)

    def totals_by_coordinates(self, *, exclude_bots: bool = False,
                             start: datetime | None = None, end: datetime | None = None,
                             site: str = "*") -> list[dict[str, object]]:
        """Count location snapshots, retaining views with missing coordinates."""
        where, params = self._filter(exclude_bots, start, end, site)
        return self._db.query(f"""
            SELECT latitude, longitude, NULLIF(country_code, '') AS country_code,
                   MAX(NULLIF(country_name, '')) AS country_name,
                   NULLIF(region_name, '') AS region_name,
                   NULLIF(city_name, '') AS city_name, COUNT(*) AS page_views
            FROM page_views v
            {where}
            GROUP BY latitude, longitude, NULLIF(country_code, ''),
                     NULLIF(region_name, ''), NULLIF(city_name, '')
            ORDER BY page_views DESC, country_name, country_code, region_name,
                     city_name, latitude, longitude
        """, params)

    def totals_by_language(self, *, exclude_bots: bool = False,
                           start: datetime | None = None, end: datetime | None = None,
                           site: str = "*") -> list[dict[str, object]]:
        """Count each visit once using its first browser language preference."""
        where, params = self._filter(exclude_bots, start, end, site)
        return self._db.query(f"""
            SELECT l.language_tag, COUNT(*) AS page_views
            FROM page_views v
            LEFT JOIN page_view_languages l ON l.page_view_id = v.page_view_id
                AND l.preference_order = 1
            {where}
            GROUP BY l.language_tag
            ORDER BY page_views DESC, l.language_tag
        """, params)

    def totals_by_referrer(self, *, exclude_bots: bool = False,
                       start: datetime | None = None, end: datetime | None = None,
                       site: str = "*") -> list[dict[str, object]]:
        """Rank referrer hosts by visits, including visits with no known referrer."""
        where, params = self._filter(exclude_bots, start, end, site)
        return self._db.query(f"""
            SELECT NULLIF(v.referrer_host, '') AS referrer_host, COUNT(*) AS page_views
            FROM page_views v
            {where}
            GROUP BY NULLIF(v.referrer_host, '')
            ORDER BY page_views DESC, referrer_host
        """, params)

    def available_sites(self) -> list[str]:
        """List sites with non-test traffic across all dates, including bots."""
        where, params = self._traffic_filter(False)
        rows = self._db.query(f"""
            SELECT DISTINCT p.site
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            ORDER BY p.site
        """, params)
        return [row["site"] for row in rows]

    def first_visit_at(self) -> datetime | None:
        """Return the earliest non-test visit across all sites, including bots."""
        where, params = self._traffic_filter(False)
        return self._db.query(
            f"SELECT MIN(v.received_at) AS first_visit_at FROM page_views v {where}", params,
        )[0]['first_visit_at']

    def recent_visits(self, *, exclude_bots: bool = False,
                      start: datetime | None = None, end: datetime | None = None,
                      before: tuple[datetime, int] | None = None,
                      site: str = "*", limit: int = DReports.PAGE_SIZE) -> list[dict[str, object]]:
        """Read a bounded page using receipt time and ID as a stable cursor."""
        where, params = self._filter(exclude_bots, start, end, site)
        if before is not None:
            where += (" AND " if where else "WHERE ") + (
                "(v.received_at < %s OR (v.received_at = %s AND v.page_view_id < %s))")
            params += (before[0], before[0], before[1])
        return self._db.query(f"""
            SELECT v.page_view_id, v.received_at, v.country_code, v.city_name, p.url
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            ORDER BY v.received_at DESC, v.page_view_id DESC LIMIT %s
        """, (*params, limit))

    def visitor_records(self, filters: dict[str, str], *, exclude_bots: bool = False,
                        before: tuple[datetime, int] | None = None,
                        limit: int = DVisitors.PAGE_SIZE) -> list[dict[str, object]]:
        """Read every stored column with literal substring filters and a stable cursor."""
        expressions = {name: (f"p.{name}" if name in ("site", "url") else
                              "HEX(v.visitor_id)" if name == "visitor_id" else f"v.{name}")
                       for name, _ in DVisitors.COLUMNS}
        expressions["languages"] = """(
            SELECT GROUP_CONCAT(l.language_tag ORDER BY l.preference_order SEPARATOR ', ')
            FROM page_view_languages l WHERE l.page_view_id = v.page_view_id
        )"""
        clauses = []
        params: tuple[object, ...] = ()
        if exclude_bots:
            condition, bot_params = self._bot_condition()
            clauses.append(f"NOT ({condition})")
            params += bot_params
        for name, value in filters.items():
            expression = expressions[name]
            clauses.append(f"CAST({expression} AS CHAR) LIKE %s ESCAPE '='")
            escaped = value.replace("=", "==").replace("%", "=%").replace("_", "=_")
            params += (f"%{escaped}%",)
        if before is not None:
            clauses.append("(v.received_at < %s OR (v.received_at = %s AND v.page_view_id < %s))")
            params += (before[0], before[0], before[1])
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        columns = ", ".join(f"{expression} AS {name}" for name, expression in expressions.items())
        return self._db.query(f"""
            SELECT {columns}
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            ORDER BY v.received_at DESC, v.page_view_id DESC LIMIT %s
        """, (*params, limit))

    def daily_totals(self, days: list[tuple[str, datetime, datetime]], *,
                     exclude_bots: bool, site: str = "*") -> list[dict[str, object]]:
        """Count indexed UTC intervals for local days, including DST and zero days.

        Explicit day boundaries avoid requiring MariaDB timezone tables and
        return one row per day rather than individual visit timestamps.
        """
        intervals = " UNION ALL ".join("SELECT %s AS day, %s AS start_at, %s AS end_at" for _ in days)
        parameters = tuple(value for day in days for value in day)
        where, filters = self._traffic_filter(exclude_bots, site)
        condition = " AND " + where.removeprefix("WHERE ") if where else ""
        return self._db.query(f"""
            SELECT d.day, COUNT(v.page_view_id) AS page_views
            FROM ({intervals}) d
            LEFT JOIN page_views v ON v.received_at >= d.start_at
                AND v.received_at < d.end_at {condition}
            GROUP BY d.day ORDER BY d.day
        """, (*parameters, *filters))

    def count_by_site(self, site: str) -> int:
        """Read the bot-filtered page-view count without recording a visit."""
        where, params = self._traffic_filter(True)
        return self._db.query(f"""
            SELECT COUNT(*) AS visits
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where} AND p.site = %s
        """, (*params, site))[0]["visits"]

    @classmethod
    def _filter(cls, exclude_bots: bool, start: datetime | None,
                end: datetime | None, site: str = "*") -> tuple[str, tuple[object, ...]]:
        where, parameters = cls._traffic_filter(exclude_bots, site)
        clauses = [where.removeprefix("WHERE ")] if where else []
        if start is not None:
            clauses.append("v.received_at >= %s")
            parameters += (start,)
        if end is not None:
            clauses.append("v.received_at < %s")
            parameters += (end,)
        return ("WHERE " + " AND ".join(clauses) if clauses else "", parameters)

    @classmethod
    def _traffic_filter(cls, exclude_bots: bool, site: str = "*") -> tuple[str, tuple[object, ...]]:
        """Exclude explicit tests on every report, and bots when requested.

        Looking up the page here also supports reports that do not join pages,
        including the daily totals' outer join that preserves empty days.
        """
        where = """WHERE NOT EXISTS (
            SELECT 1 FROM pages test_page WHERE test_page.page_id = v.page_id
                AND (LEFT(test_page.site, %s) = %s OR test_page.url REGEXP %s)
        )"""
        params: tuple[object, ...] = (
            len(DReports.TEST_SITE_PREFIX), DReports.TEST_SITE_PREFIX,
            DReports.TEST_PAGE_URL_PATTERN,
        )
        if exclude_bots:
            condition, bot_params = cls._bot_condition()
            where += f" AND NOT ({condition})"
            params += bot_params
        if site != "*":
            where += """ AND EXISTS (
                SELECT 1 FROM pages site_page
                WHERE site_page.page_id = v.page_id AND site_page.site = %s
            )"""
            params += (site,)
        return where, params

    @staticmethod
    def _bot_condition() -> tuple[str, tuple[object, ...]]:
        """Recognize known automation even when its stored bot flag is false."""
        families = DVisitorDetails.BOT_BROWSER_FAMILIES
        placeholders = ", ".join("%s" for _ in families)
        tokens = DVisitorDetails.BOT_USER_AGENT_TOKENS
        agent_conditions = " OR ".join(
            "LOCATE(%s, LOWER(COALESCE(v.user_agent, ''))) > 0" for _ in tokens
        )
        profile_condition, profile_params = VisitDb._automation_profile_condition()
        return (f"COALESCE(v.is_bot, 0) = 1 "
                f"OR COALESCE(v.browser_family, '') IN ({placeholders}) "
                f"OR {agent_conditions} "
                "OR COALESCE(JSON_UNQUOTE(JSON_EXTRACT(v.client_details, '$.webdriver')), "
                "'false') = 'true' "
                f"OR {profile_condition}", families + tokens + profile_params)

    @staticmethod
    def _automation_profile_condition() -> tuple[str, tuple[object, ...]]:
        """Apply BrowserAutomation's profiles without rewriting historical flags.

        COALESCE keeps incomplete metadata from turning NOT(bot) into SQL NULL.
        """
        desktop_os = DVisitorDetails.BOT_DESKTOP_OS_FAMILIES
        desktop_platforms = DVisitorDetails.BOT_IOS_DESKTOP_PLATFORMS
        os_placeholders = ", ".join("%s" for _ in desktop_os)
        platform_placeholders = ", ".join("%s" for _ in desktop_platforms)
        return (f"""COALESCE(
            JSON_VALUE(v.client_details, '$.vendor') = %s AND (
                (v.device_category = %s
                 AND JSON_VALUE(v.client_details, '$.platform') = %s
                 AND JSON_VALUE(v.client_details, '$.screen_width') = %s
                 AND JSON_VALUE(v.client_details, '$.screen_height') = %s
                 AND JSON_VALUE(v.client_details, '$.device_memory') = %s
                 AND JSON_VALUE(v.client_details, '$.max_touch_points') = %s
                 AND JSON_VALUE(v.client_details, '$.hardware_concurrency') >= %s)
                OR (v.os_family IN ({os_placeholders})
                    AND JSON_VALUE(v.client_details, '$.platform') = %s)
                OR (JSON_VALUE(v.client_details, '$.screen_width') = %s
                    AND JSON_VALUE(v.client_details, '$.screen_height') = %s
                    AND JSON_VALUE(v.client_details, '$.viewport_width') > %s)
                OR (JSON_VALUE(v.client_details, '$.platform') = %s
                    AND JSON_VALUE(v.client_details, '$.screen_width') = %s
                    AND JSON_VALUE(v.client_details, '$.screen_height') = %s
                    AND JSON_VALUE(v.client_details, '$.device_memory') = %s
                    AND v.referrer_host = %s)
                OR (v.os_family = %s
                    AND JSON_VALUE(v.client_details, '$.platform') IN ({platform_placeholders})
                    AND JSON_VALUE(v.client_details, '$.max_touch_points') = %s)
            ), 0)""", (
                DVisitorDetails.BOT_CLIENT_VENDOR,
                "mobile", DVisitorDetails.BOT_LINUX_PLATFORM,
                *DVisitorDetails.BOT_PHONE_SCREEN, DVisitorDetails.BOT_RENDERER_MEMORY,
                DVisitorDetails.BOT_PHONE_TOUCH_POINTS, DVisitorDetails.BOT_PHONE_MIN_CPUS,
                *desktop_os, DVisitorDetails.BOT_LINUX_PLATFORM,
                *DVisitorDetails.BOT_RENDERER_SCREEN, DVisitorDetails.BOT_RENDERER_SCREEN[0],
                DVisitorDetails.BOT_PREVIEW_PLATFORM, *DVisitorDetails.BOT_PREVIEW_SCREEN,
                DVisitorDetails.BOT_RENDERER_MEMORY, DVisitorDetails.BOT_PREVIEW_REFERRER,
                "iOS", *desktop_platforms, DVisitorDetails.BOT_IPHONE_TOUCH_POINTS,
            ))

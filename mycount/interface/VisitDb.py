"""Persist a processed visit through the shared database bridge."""

from datetime import timezone
import json

from mycount.entity.Visit import Visit
from mycount.constants.DVisitorDetails import DVisitorDetails
from mycount.interface.DbMgr import DbMgr


class VisitDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

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

    def totals_by_page(self, *, exclude_bots: bool = False) -> list[dict[str, object]]:
        """Rank visited pages within each site by views, breaking ties by URL."""
        where, params = self._bot_filter(exclude_bots)
        return self._db.query(f"""
            SELECT p.site, p.url, COUNT(*) AS page_views,
                   MAX(v.received_at) AS last_visited
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            GROUP BY p.page_id, p.site, p.url
            ORDER BY p.site, page_views DESC, p.url
        """, params)

    def totals_by_site(self, *, exclude_bots: bool = False) -> list[dict[str, object]]:
        """Count recorded browser IDs separately from views with no identifier.

        IDs are scoped to each site. Browser counts include automated clients;
        known bot views are reported separately, not treated as people.
        """
        where, params = self._bot_filter(exclude_bots)
        return self._db.query(f"""
            SELECT p.site, COUNT(*) AS page_views, MAX(v.received_at) AS last_visited,
                   COUNT(DISTINCT v.visitor_id) AS unique_browsers,
                   COUNT(CASE WHEN v.visitor_id IS NULL THEN 1 END) AS unidentified_views,
                   COUNT(CASE WHEN v.is_bot = 1 THEN 1 END) AS known_bot_views
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            GROUP BY p.site
            ORDER BY page_views DESC, p.site
        """, params)

    def totals_by_location(self, *, exclude_bots: bool = False) -> list[dict[str, object]]:
        """Rank all recorded views by country, state/province, and city."""
        where, params = self._bot_filter(exclude_bots)
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

    def totals_by_referrer(self, *, exclude_bots: bool = False) -> list[dict[str, object]]:
        """Rank referrer hosts by visits, including visits with no known referrer."""
        where, params = self._bot_filter(exclude_bots)
        return self._db.query(f"""
            SELECT NULLIF(v.referrer_host, '') AS referrer_host, COUNT(*) AS page_views
            FROM page_views v
            {where}
            GROUP BY NULLIF(v.referrer_host, '')
            ORDER BY page_views DESC, referrer_host
        """, params)

    def recent_visits(self, *, exclude_bots: bool = False) -> list[dict[str, object]]:
        """Return all matching visits, newest ID first for time ties."""
        where, params = self._bot_filter(exclude_bots)
        return self._db.query(f"""
            SELECT v.received_at, v.country_code, v.city_name, p.url
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where}
            ORDER BY v.received_at DESC, v.page_view_id DESC
        """, params)

    def count_by_site(self, site: str) -> int:
        """Read the bot-filtered page-view count without recording a visit."""
        where, params = self._bot_filter(True)
        return self._db.query(f"""
            SELECT COUNT(*) AS visits
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            {where} AND p.site = %s
        """, (*params, site))[0]["visits"]

    @staticmethod
    def _bot_filter(exclude_bots: bool) -> tuple[str, tuple[str, ...]]:
        if not exclude_bots:
            return "", ()
        families = DVisitorDetails.BOT_BROWSER_FAMILIES
        placeholders = ", ".join("%s" for _ in families)
        return (f"WHERE COALESCE(v.is_bot, 0) = 0 "
                f"AND COALESCE(v.browser_family, '') NOT IN ({placeholders})", families)

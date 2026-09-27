"""Persist a processed visit through the shared database bridge."""

from datetime import timezone
import json

from mycount.entity.Visit import Visit
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
                    (page_id, received_at, country_code, region_code, region_name,
                     city_name, browser_family, os_family, device_category,
                     fingerprint, fingerprint_version, referrer_host, user_agent,
                     browser_version, os_version, device_brand, device_model, is_bot, client_details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                page_id, visit.received_at.astimezone(timezone.utc).replace(tzinfo=None),
                visit.country_code, visit.region_code, visit.region_name, visit.city_name,
                visit.browser_family, visit.os_family, visit.device_category,
                visit.fingerprint, visit.fingerprint_version,
                visit.referrer_host, visit.user_agent, visit.browser_version, visit.os_version,
                visit.device_brand, visit.device_model, visit.is_bot,
                json.dumps(dict(visit.client_details), allow_nan=False) if visit.client_details else None,
            ))
            for position, language in enumerate(visit.languages, start=1):
                self._db.execute(
                    "INSERT INTO page_view_languages "
                    "(page_view_id, preference_order, language_tag) VALUES (%s, %s, %s)",
                    (view_id, position, language),
                )
        return view_id

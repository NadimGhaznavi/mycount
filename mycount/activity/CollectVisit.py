"""Coordinate visit preparation and persistence."""

from dataclasses import replace

from mycount.activity.BrowserMetadata import BrowserMetadata
from mycount.interface.DbMgr import DbMgr
from mycount.interface.GeoIp import GeoIp
from mycount.interface.VisitDb import VisitDb
from mycount.interface.VisitPayload import VisitPayload


class CollectVisit:
    def __init__(self, payload: VisitPayload, browser: BrowserMetadata) -> None:
        self._payload = payload
        self._browser = browser

    def record(self, payload: object, address: str, origin: str) -> int:
        visit, user_agent = self._payload.resolve(payload, origin)
        visit = self._browser.enrich(visit, user_agent)
        db = DbMgr()
        try:
            location = GeoIp(db).locate(address)
            visit = replace(visit, country_code=location.country_code,
                            region_code=location.region_code, region_name=location.region_name,
                            city_name=location.city_name)
            return VisitDb(db).record(visit)
        finally:
            db.close()

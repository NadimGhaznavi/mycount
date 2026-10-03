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
        location = GeoIp().locate(address)
        db = DbMgr()
        try:
            visit = replace(visit, ip_address=address, country_code=location.country_code,
                            country_name=location.country_name, region_name=location.region_name,
                            city_name=location.city_name,
                            latitude=location.latitude, longitude=location.longitude,
                            zip=location.zip, timezone=location.timezone)
            return VisitDb(db).record(visit)
        finally:
            db.close()

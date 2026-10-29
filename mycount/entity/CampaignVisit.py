"""Persisted facts used to recognize a distributed crawl within one site."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CampaignVisit:
    page_view_id: int
    site: str
    url: str
    received_at: datetime
    visitor_id: bytes
    ip_address: str
    referrer_host: str | None

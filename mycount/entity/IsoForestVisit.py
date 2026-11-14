"""Raw page-view inputs, with no existing bot classifications."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IsoForestVisit:
    page_view_id: int
    received_at: datetime
    site: str
    url: str
    ip_address: str | None
    user_agent: str | None
    client_details: tuple[tuple[str, str | int | float | bool | None], ...]
    geoip_timezone: str | None = None
    os_family: str | None = None
    primary_language: str | None = None
    referrer_host: str | None = None

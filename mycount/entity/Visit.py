"""Application data for one visit, independent of database persistence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class Visit:
    """Validated visit data passed between processing activities.

    The receiving interface supplies an aware UTC receipt time and a URL
    containing only the origin and path. Languages retain preference order.
    Unknown metadata is None; fingerprint and version are supplied together.
    Activities can use dataclasses.replace to return an enriched visit.
    Optional client details are immutable key/value pairs. The validated
    user-agent string is retained; database-generated IDs remain outside this entity.
    """

    site: str
    url: str
    received_at: datetime
    languages: tuple[str, ...] = ()
    country_code: str | None = None
    region_code: str | None = None
    region_name: str | None = None
    city_name: str | None = None
    browser_family: str | None = None
    os_family: str | None = None
    device_category: Literal["desktop", "mobile", "tablet", "other"] | None = None
    fingerprint: bytes | None = None
    fingerprint_version: int | None = None
    visitor_id: bytes | None = None
    referrer_host: str | None = None
    user_agent: str | None = None
    browser_version: str | None = None
    os_version: str | None = None
    device_brand: str | None = None
    device_model: str | None = None
    is_bot: bool | None = None
    client_details: tuple[tuple[str, str | int | float | bool], ...] = ()

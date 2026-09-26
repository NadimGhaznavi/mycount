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
    Raw request data and database-generated IDs remain outside this entity.
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

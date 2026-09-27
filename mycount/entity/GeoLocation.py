"""Approximate geographic metadata without a source address."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeoLocation:
    continent: str | None = None
    country_code: str | None = None
    region_name: str | None = None
    city_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    zip: str | None = None
    timezone: str | None = None

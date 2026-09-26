"""Approximate geographic metadata without a source address."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeoLocation:
    country_code: str | None = None
    region_code: str | None = None
    region_name: str | None = None
    city_name: str | None = None

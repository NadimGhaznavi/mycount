"""A public reference range imported from the upstream dataset."""

from dataclasses import dataclass

from mycount.entity.GeoLocation import GeoLocation


@dataclass(frozen=True)
class GeoIpRange:
    version: int
    start: bytes
    end: bytes
    location: GeoLocation

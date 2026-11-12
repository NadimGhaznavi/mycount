"""One site's activity within a network block and fixed UTC window."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IsoForestObservation:
    window_start: datetime
    network_block: str
    site: str
    page_view_ids: tuple[int, ...]
    distinct_ips: int
    features: tuple[float, ...]

"""A validated promotional posting event."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MarketingPost:
    posted_at: datetime
    platform: str
    url: str
    notes: str
    screenshot_path: str | None = None

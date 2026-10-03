"""A validated promotional posting event."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class MarketingPost:
    posted_at: datetime
    platform: str
    url: str
    notes: str
    screenshot_path: str | None = None
    submission_id: str = field(default_factory=lambda: uuid4().hex)

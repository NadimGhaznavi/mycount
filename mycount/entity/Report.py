"""A consistent report snapshot prepared for presentation."""

from dataclasses import dataclass, field
from datetime import datetime

from mycount.entity.ReportOptions import ReportOptions


@dataclass(frozen=True)
class Report:
    options: ReportOptions
    daily: list[dict[str, object]]
    first_visit_at: datetime | None
    sites: list[dict[str, object]] = field(default_factory=list)
    pages: list[dict[str, object]] = field(default_factory=list)
    locations: list[dict[str, object]] = field(default_factory=list)
    recent: list[dict[str, object]] = field(default_factory=list)
    referrers: list[dict[str, object]] = field(default_factory=list)
    posts: list[dict[str, object]] = field(default_factory=list)
    older: tuple[datetime, int] | None = None

"""Validated date range, timezone, and recent-visit position."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ReportOptions:
    start: date
    end: date
    timezone: str
    exclude_bots: bool = True
    before: tuple[datetime, int] | None = None

    def day_ranges(self) -> list[tuple[str, datetime, datetime]]:
        zone = ZoneInfo(self.timezone)
        days = []
        day = self.start
        while day <= self.end:
            following = day + timedelta(days=1)
            start = datetime.combine(day, time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
            end = datetime.combine(following, time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
            days.append((day.isoformat(), start, end))
            day = following
        return days

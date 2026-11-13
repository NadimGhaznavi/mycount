"""Validated report filters and recent-visit position."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from mycount.constants.DTrafficFilters import DTrafficFilters


@dataclass(frozen=True)
class ReportOptions:
    start: date
    end: date
    timezone: str
    filter_mode: str = DTrafficFilters.DEFAULT
    before: tuple[datetime, int] | None = None
    site: str = "*"

    @property
    def exclude_bots(self) -> bool:
        return DTrafficFilters.BASIC in DTrafficFilters.MODULES[self.filter_mode]

    @property
    def uses_isoforest(self) -> bool:
        return "isoforest" in DTrafficFilters.MODULES[self.filter_mode]

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

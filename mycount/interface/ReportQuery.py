"""Validate incoming report filters and build pagination links."""

from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mycount.constants.DReports import DReports
from mycount.entity.ReportOptions import ReportOptions


class ReportQuery:
    @staticmethod
    def resolve(query: dict[str, list[str]]) -> ReportOptions:
        def field(name: str, default: str) -> str:
            values = query.get(name, [default])
            if len(values) != 1:
                raise ValueError(f"Supply one {name} value.")
            return values[0]

        timezone = field("timezone", "UTC")
        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Choose a valid report timezone.") from error
        today = datetime.now(zone).date()
        try:
            end = date.fromisoformat(field("end", today.isoformat()))
            start = date.fromisoformat(field("start", (end - timedelta(days=DReports.DEFAULT_DAYS - 1)).isoformat()))
            if end == date.max or not 0 <= (end - start).days < DReports.MAX_DAYS:
                raise ValueError
        except (ValueError, OverflowError) as error:
            raise ValueError(f"Choose a date range of 1 to {DReports.MAX_DAYS} days.") from error
        before = None
        cursor = field("before", "")
        if cursor:
            try:
                timestamp, identifier = cursor.split(",")
                received_at = datetime.fromisoformat(timestamp)
                view_id = int(identifier)
                if received_at.tzinfo is not None or not 0 < view_id < 2**64:
                    raise ValueError
                before = (received_at, view_id)
            except (ValueError, OverflowError) as error:
                raise ValueError("Invalid recent-visit position.") from error
        bots = query.get("exclude_bots", ["1"])[-1]
        if bots not in ("0", "1"):
            raise ValueError("Invalid bot filter.")
        return ReportOptions(start, end, timezone, bots == "1", before)

    @staticmethod
    def link(path: str, options: ReportOptions, before: tuple[datetime, int] | None = None) -> str:
        query = {"start": options.start.isoformat(), "end": options.end.isoformat(),
                 "timezone": options.timezone, "exclude_bots": "1" if options.exclude_bots else "0"}
        if before is not None:
            query["before"] = f"{before[0].isoformat()},{before[1]}"
        return path + "?" + urlencode(query)

"""Validate visitor column filters and preserve them in pagination links."""

from datetime import datetime
from urllib.parse import urlencode

from mycount.constants.DVisitors import DVisitors


class VisitorsQuery:
    @staticmethod
    def filters(query: dict[str, list[str]]) -> dict[str, str]:
        filters = {}
        for name, _ in DVisitors.COLUMNS:
            values = query.get(name, [""])
            if len(values) != 1:
                raise ValueError(f"Supply one {name} filter.")
            if values[0]:
                filters[name] = values[0]
        return filters

    @staticmethod
    def link(filters: dict[str, str], before: tuple[datetime, int] | None = None) -> str:
        query = dict(filters)
        if before is not None:
            query["before"] = f"{before[0].isoformat()},{before[1]}"
        return "/visitors" + ("?" + urlencode(query) if query else "")

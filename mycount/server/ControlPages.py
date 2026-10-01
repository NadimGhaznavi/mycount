"""Render the control server's presentation assets."""

from pathlib import Path
from datetime import datetime, timezone

import pycountry

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class ControlPages:
    def __init__(self) -> None:
        self._templates = Environment(
            loader=FileSystemLoader(Path(__file__).with_name("templates")),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
        )
        self._templates.filters["country_flag"] = self._country_flag
        self._templates.filters["utc_iso"] = lambda value: value.replace(tzinfo=timezone.utc).isoformat()

    def render(self, sites: list[dict[str, object]], pages: list[dict[str, object]],
               locations: list[dict[str, object]], recent: list[dict[str, object]],
               referrers: list[dict[str, object]], *, first_visit_at: datetime | None = None,
               exclude_bots: bool = True, error: str | None = None) -> bytes:
        pages_by_site = {}
        for page in pages:
            pages_by_site.setdefault(page["site"], []).append(page)
        return self._templates.get_template("control.html").render(
            sites=sites, pages_by_site=pages_by_site, locations=locations, recent=recent, referrers=referrers,
            country_slices=self._country_slices(locations),
            traffic_times=[visit["received_at"].replace(tzinfo=timezone.utc).isoformat() for visit in recent],
            first_visit_at=first_visit_at,
            error=error, exclude_bots=exclude_bots, refreshed_at=datetime.now(timezone.utc), active_page="metrics",
        ).encode("utf-8")

    @staticmethod
    def _country_slices(locations: list[dict[str, object]]) -> list[dict[str, object]]:
        countries = {}
        for location in locations:
            code = (location["country_code"] or "").upper()
            country = countries.setdefault(code, {
                "name": location["country_name"] or code or "Unknown", "visits": 0,
            })
            country["visits"] += location["page_views"]
        ordered = sorted(countries.values(), key=lambda country: (-country["visits"], country["name"]))
        total = sum(country["visits"] for country in ordered)
        slices = []
        for country in ordered:
            slices.append({
                **country,
                "percent": country["visits"] / total * 100,
            })
        return slices

    def reference(self, first_visit_at: datetime | None = None) -> bytes:
        return self._templates.get_template("reference.html").render(
            refreshed_at=datetime.now(timezone.utc), active_page="reference", first_visit_at=first_visit_at,
        ).encode("utf-8")

    @staticmethod
    def _country_flag(code: str | None) -> str:
        code = (code or "").upper()
        if pycountry.countries.get(alpha_2=code) is None:
            return ""
        return "".join(chr(ord(character) - ord("A") + 0x1F1E6) for character in code)

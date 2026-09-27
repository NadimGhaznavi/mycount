"""Render the control server's presentation assets."""

from pathlib import Path
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class ControlPages:
    def __init__(self) -> None:
        self._templates = Environment(
            loader=FileSystemLoader(Path(__file__).with_name("templates")),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
        )
        self._templates.filters["utc_iso"] = lambda value: value.replace(tzinfo=timezone.utc).isoformat()

    def render(self, sites: list[dict[str, object]], pages: list[dict[str, object]],
               *, error: str | None = None) -> bytes:
        pages_by_site = {}
        for page in pages:
            pages_by_site.setdefault(page["site"], []).append(page)
        return self._templates.get_template("control.html").render(
            sites=sites, pages_by_site=pages_by_site,
            error=error, refreshed_at=datetime.now(timezone.utc), active_page="metrics",
        ).encode("utf-8")

    def reference(self) -> bytes:
        return self._templates.get_template("reference.html").render(
            refreshed_at=datetime.now(timezone.utc), active_page="reference",
        ).encode("utf-8")

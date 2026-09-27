"""Render the control server's presentation assets."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class ControlPages:
    def __init__(self) -> None:
        self._templates = Environment(
            loader=FileSystemLoader(Path(__file__).with_name("templates")),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
        )

    def render(self) -> bytes:
        return self._templates.get_template("control.html").render().encode("utf-8")

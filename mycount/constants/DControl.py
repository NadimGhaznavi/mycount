"""Defaults for the standalone control server."""

from typing import Final


class DControl:
    SERVICE_UNIT: Final[str] = "mycount-control.service"
    HOST: Final[str] = "0.0.0.0"
    PORT: Final[int] = 61777

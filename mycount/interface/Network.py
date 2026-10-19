"""Resolve network defaults and production overrides once per process."""

from functools import cache
from pathlib import Path

from mycount.constants.DMyCount import DMyCount
from mycount.interface.Configuration import Configuration


class Network:
    @staticmethod
    def binding(use: str) -> tuple[str, int]:
        path = Path(DMyCount.BASE_DIR) / DMyCount.CONFIG_FILE
        return Network._bindings(path, DMyCount.CMDB_NETWORK)[use]

    @staticmethod
    def destination(use: str) -> tuple[str, int]:
        interface, port = Network.binding(use)
        return ('127.0.0.1' if interface == '0.0.0.0' else interface, port)

    @staticmethod
    @cache
    def _bindings(path: Path, defaults: tuple[tuple[str, str, int], ...]) -> dict[str, tuple[str, int]]:
        return Configuration.read(path, defaults)

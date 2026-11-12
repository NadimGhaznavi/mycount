"""Reuse the city scheduler's cron contract, with a separate worker lock and run request."""

from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime
import fcntl
from pathlib import Path

from mycount.constants.DIsoForest import DIsoForest
from mycount.interface.CitySchedule import CitySchedule


class IsoForestSchedule:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else Path(__file__).resolve().parents[2] / DIsoForest.DIRECTORY
        self._schedule = CitySchedule(self.directory, default_expression=DIsoForest.DEFAULT_SCHEDULE)

    def read(self) -> dict[str, object]:
        return self._schedule.read()

    def update(self, enabled: bool, expression: str) -> dict[str, object]:
        return self._schedule.update(enabled, expression)

    def install(self) -> dict[str, object]:
        return self._schedule.install()

    def due(self, now: datetime) -> bool:
        return self._schedule.due(now)

    def requested(self) -> bool:
        return (self.directory / "run.request").exists()

    def request_run(self) -> None:
        with self._schedule.lock():
            (self.directory / "run.request").touch()

    def claim_request(self) -> None:
        with self._schedule.lock():
            (self.directory / "run.request").unlink(missing_ok=True)

    @contextmanager
    def worker_lock(self) -> Iterator[bool]:
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "run.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
            else:
                yield True

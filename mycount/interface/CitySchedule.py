"""Persist validated refresh settings for the unprivileged cron launcher."""

from contextlib import contextmanager
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from crontab import CronSlices

from mycount.constants.DCities import DCities


class CitySchedule:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else Path(__file__).resolve().parents[2] / DCities.DIRECTORY

    @staticmethod
    def validate(enabled: bool, expression: str) -> dict[str, object]:
        if (type(enabled) is not bool or not isinstance(expression, str)
                or len(expression) > 255 or "\n" in expression or "\r" in expression):
            raise ValueError("Provide an enabled flag and a five-field cron expression.")
        expression = " ".join(expression.split())
        if len(expression.split()) != 5 or not CronSlices.is_valid(expression):
            raise ValueError("Use five cron fields: minute hour day-of-month month day-of-week.")
        return {"enabled": enabled, "expression": expression}

    def read(self) -> dict[str, object]:
        try:
            values = json.loads((self.directory / "schedule.json").read_text())
        except FileNotFoundError:
            return self.validate(True, DCities.DEFAULT_SCHEDULE)
        if not isinstance(values, dict) or values.keys() != {"enabled", "expression"}:
            raise ValueError("Invalid city refresh schedule file.")
        return self.validate(**values)

    @contextmanager
    def lock(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "schedule.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def _write(self, values: dict[str, object]) -> None:
        with NamedTemporaryFile(mode="w", dir=self.directory, prefix=".schedule-", delete=False) as stream:
            candidate = Path(stream.name)
            try:
                json.dump(values, stream)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
                candidate.chmod(0o644)
                candidate.replace(self.directory / "schedule.json")
            finally:
                candidate.unlink(missing_ok=True)

    def update(self, enabled: bool, expression: str) -> dict[str, object]:
        values = self.validate(enabled, expression)
        with self.lock():
            self._write(values)
        return values

    def install(self) -> dict[str, object]:
        """Retain custom and disabled schedules during installation and upgrade."""
        with self.lock():
            values = self.read()
            self._write(values)
        return values

    def due(self, now: datetime) -> bool:
        values = self.read()
        if not values["enabled"]:
            return False
        fields = values["expression"].split()
        slices = CronSlices(values["expression"])
        if any(value not in list(slices[index]) for index, value in
               ((0, now.minute), (1, now.hour), (3, now.month))):
            return False
        day = now.day in list(slices[2])
        weekday = (now.weekday() + 1) % 7 in [value % 7 for value in slices[4]]
        # Cron ORs restricted day-of-month and day-of-week fields.
        return day and weekday if fields[2].startswith("*") or fields[4].startswith("*") else day or weekday


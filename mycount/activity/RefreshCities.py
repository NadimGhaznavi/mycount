"""Refresh the city reference file manually or through the cron launcher."""

import argparse
from datetime import datetime
import fcntl
import logging
from tempfile import TemporaryDirectory
from pathlib import Path

from mycount.interface.CityLocations import CityLocations
from mycount.interface.CitySchedule import CitySchedule
from mycount.interface.GeoNamesSource import GeoNamesSource


class RefreshCities:
    def __init__(self, cities: CityLocations, schedule: CitySchedule, source: GeoNamesSource) -> None:
        self._cities = cities
        self._schedule = schedule
        self._source = source

    def run(self, *, scheduled: bool = False) -> bool:
        directory = self._cities.directory
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "refresh.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            if scheduled:
                now = datetime.now().astimezone()
                if not self._schedule.read()["enabled"]:
                    return False
                status = self._cities.status()
                if status["available"]:
                    if not self._schedule.due(now):
                        return False
                    if datetime.fromisoformat(status["refreshed_at"]) >= now.replace(second=0, microsecond=0):
                        return False
            with TemporaryDirectory(prefix=".refresh-", dir=directory) as temporary:
                staging = Path(temporary)
                self._source.download(staging)
                count = self._cities.build(staging)
                self._cities.publish(staging)
            logging.info("GeoNames city data refreshed: %s cities", count)
            return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheduled", action="store_true", help="Apply saved schedule; initialize missing data when enabled")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    RefreshCities(CityLocations(), CitySchedule(), GeoNamesSource()).run(scheduled=args.scheduled)


if __name__ == "__main__":
    main()


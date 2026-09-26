"""Refresh both public address families without interrupting lookups."""

from itertools import islice
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount
from mycount.interface.DatabaseEnvironment import DatabaseEnvironment
from mycount.interface.DbMgr import DbMgr
from mycount.interface.GeoIpImportDb import GeoIpImportDb
from mycount.interface.GeoIpSource import GeoIpSource


class UpdateGeoIp:
    def __init__(self, source: GeoIpSource, database: GeoIpImportDb) -> None:
        self._source = source
        self._database = database

    def run(self) -> dict[int, int]:
        counts = {}
        with TemporaryDirectory(prefix="mycount-geoip-") as directory:
            with self._database.refresh():
                for version in DGeoIp.VERSIONS:
                    archive = Path(directory) / f"ipv{version}.zip"
                    self._source.download(version, archive)
                    rows = self._source.rows(archive, version)
                    count = 0
                    while batch := list(islice(rows, DGeoIp.BATCH_SIZE)):
                        self._database.append(batch)
                        count += len(batch)
                    if count == 0:
                        raise ValueError(f"The IPv{version} database is empty.")
                    counts[version] = count
        return counts


if __name__ == "__main__":
    os.environ.update(DatabaseEnvironment.read(Path(DMyCount.DATABASE_ENV)))
    db = DbMgr()
    try:
        counts = UpdateGeoIp(GeoIpSource(), GeoIpImportDb(db)).run()
        print("GeoIP refreshed: " + ", ".join(f"IPv{v}: {n} ranges" for v, n in counts.items()))
    finally:
        db.close()

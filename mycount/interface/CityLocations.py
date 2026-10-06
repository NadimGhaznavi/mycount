"""Build and query an independent, atomically replaced GeoNames reference file."""

from datetime import datetime, timezone
from contextlib import closing
from io import TextIOWrapper
from pathlib import Path
import sqlite3
from unicodedata import normalize
from zipfile import ZipFile

import pycountry

from mycount.constants.DCities import DCities


class CityLocations:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else Path(__file__).resolve().parents[2] / DCities.DIRECTORY
        self.path = self.directory / "cities.sqlite"

    @staticmethod
    def _name(value: str) -> str:
        return " ".join(normalize("NFKC", value).casefold().split())

    def build(self, staging: Path) -> int:
        regions = {}
        for line in (staging / "admin1CodesASCII.txt").read_text(encoding="utf-8").splitlines():
            fields = line.split("\t")
            if len(fields) != 4 or not fields[0] or not fields[1]:
                raise ValueError("Invalid GeoNames administrative region record.")
            regions[fields[0]] = (self._name(fields[1]), self._name(fields[2]))
        if not regions:
            raise ValueError("GeoNames administrative region data is empty.")
        with closing(sqlite3.connect(staging / "cities.sqlite")) as db, db:
            db.executescript("""
                CREATE TABLE cities (id INTEGER PRIMARY KEY, country TEXT, region TEXT,
                    region_name TEXT, region_ascii TEXT, latitude REAL, longitude REAL);
                CREATE TABLE names (name TEXT, city_id INTEGER, PRIMARY KEY (name, city_id));
                CREATE TABLE metadata (refreshed_at TEXT, city_count INTEGER);
            """)
            count = 0
            with ZipFile(staging / "cities500.zip") as archive:
                if archive.getinfo("cities500.txt").file_size > DCities.MAX_EXTRACT_BYTES:
                    raise ValueError("GeoNames city file exceeds the size limit.")
                with archive.open("cities500.txt") as raw, TextIOWrapper(raw, encoding="utf-8") as stream:
                    for line in stream:
                        fields = line.rstrip("\r\n").split("\t")
                        if len(fields) != 19 or not fields[1] or fields[6] != "P":
                            raise ValueError("Invalid GeoNames city record.")
                        city_id = int(fields[0])
                        latitude, longitude = float(fields[4]), float(fields[5])
                        if city_id <= 0 or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                            raise ValueError("Invalid GeoNames city coordinates.")
                        country, region = fields[8], fields[10]
                        if len(country) != 2 or not country.isascii() or not country.isalpha():
                            raise ValueError("Invalid GeoNames city country code.")
                        region_names = regions.get(f"{country}.{region}", ("", ""))
                        db.execute("INSERT INTO cities VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (city_id, country, self._name(region), *region_names, latitude, longitude))
                        names = {self._name(name) for name in [fields[1], fields[2], *fields[3].split(",")] if name.strip()}
                        db.executemany("INSERT INTO names VALUES (?, ?)", ((name, city_id) for name in names))
                        count += 1
            if not count:
                raise ValueError("GeoNames city data is empty.")
            db.execute("INSERT INTO metadata VALUES (?, ?)", (datetime.now(timezone.utc).isoformat(), count))
        return count

    def publish(self, staging: Path) -> None:
        candidate = staging / "cities.sqlite"
        candidate.chmod(0o644)
        candidate.replace(self.path)

    def _open(self):
        return sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)

    def status(self) -> dict[str, object]:
        if not self.path.exists():
            return {"available": False, "refreshed_at": None, "city_count": 0}
        with closing(self._open()) as db:
            refreshed_at, count = db.execute("SELECT refreshed_at, city_count FROM metadata").fetchone()
        return {"available": True, "refreshed_at": refreshed_at, "city_count": count}

    def locate(self, locations: list[dict[str, object]]) -> list[tuple[float, float] | None]:
        """Resolve exact city aliases; leave absent or ambiguous matches unresolved."""
        if not self.path.exists():
            return [None] * len(locations)
        results = []
        with closing(self._open()) as db:
            for location in locations:
                country = location["country_code"]
                if not country and location["country_name"]:
                    try:
                        country = pycountry.countries.lookup(location["country_name"]).alpha_2
                    except LookupError:
                        results.append(None)
                        continue
                clauses = ["n.name = ?"]
                params = [self._name(location["city_name"])]
                if country:
                    clauses.append("c.country = ?")
                    params.append(country.upper())
                region = location["region_name"]
                if region:
                    if country:
                        subdivision = pycountry.subdivisions.get(code=f"{country.upper()}-{region.upper()}")
                        if subdivision is not None:
                            region = subdivision.name
                    clauses.append("(c.region = ? OR c.region_name = ? OR c.region_ascii = ?)")
                    params.extend([self._name(region)] * 3)
                rows = db.execute("SELECT DISTINCT c.id, c.latitude, c.longitude FROM names n "
                                  "JOIN cities c ON c.id = n.city_id WHERE " + " AND ".join(clauses) + " LIMIT 2", params).fetchall()
                results.append((rows[0][1], rows[0][2]) if len(rows) == 1 else None)
        return results

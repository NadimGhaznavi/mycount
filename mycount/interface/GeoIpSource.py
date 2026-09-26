"""Download and decode the upstream zipped CSV databases."""

from collections.abc import Iterator
import csv
from io import TextIOWrapper
from ipaddress import ip_address
from pathlib import Path
import shutil
from urllib.request import urlopen
from zipfile import ZipFile

from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount
from mycount.entity.GeoIpRange import GeoIpRange
from mycount.entity.GeoLocation import GeoLocation


class GeoIpSource:
    def download(self, version: int, destination: Path) -> None:
        with urlopen(DGeoIp.URL.format(version=version), timeout=DGeoIp.DOWNLOAD_TIMEOUT) as response:
            with destination.open("wb") as output:
                shutil.copyfileobj(response, output)

    def rows(self, archive: Path, version: int) -> Iterator[GeoIpRange]:
        with ZipFile(archive) as zipped:
            with zipped.open(DGeoIp.MEMBER.format(version=version)) as stream:
                reader = csv.DictReader(TextIOWrapper(stream, encoding="utf-8", newline=""))
                if reader.fieldnames != list(DGeoIp.COLUMNS):
                    raise ValueError("Unexpected GeoIP CSV header.")
                for line, row in enumerate(reader, start=2):
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError(f"Incomplete GeoIP row at line {line}.")
                    start, end = ip_address(row["start_ip"]), ip_address(row["end_ip"])
                    if (row["ip_version"] != str(version) or start.version != version
                            or end.version != version or int(start) > int(end)):
                        raise ValueError(f"Invalid GeoIP range at line {line}.")
                    country = row["country_code"] or None
                    region, city = row["state"] or None, row["city"] or None
                    if (country is not None and (len(country) != 2 or not country.isascii())
                            or len(region or "") > DGeoIp.REGION_NAME_LENGTH
                            or len(city or "") > DMyCount.CITY_NAME_LENGTH):
                        raise ValueError(f"Invalid GeoIP location at line {line}.")
                    yield GeoIpRange(version, int(start).to_bytes(16, "big"),
                                     int(end).to_bytes(16, "big"),
                                     GeoLocation(country_code=country, region_name=region, city_name=city))

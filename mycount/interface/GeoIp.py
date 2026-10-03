"""Translate BMGeoIP HTTP lookups into MyCount location snapshots."""

from ipaddress import ip_address
from http.client import HTTPException
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount
from mycount.entity.GeoLocation import GeoLocation
from mycount.interface.GeoIpUnavailable import GeoIpUnavailable


class GeoIp:
    def locate(self, address: str) -> GeoLocation:
        ip = ip_address(address)
        if ip.version == 6 and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            return GeoLocation()
        url = f"http://{DGeoIp.HOST}:{DGeoIp.PORT}/api/lookup?{urlencode({'ip': str(ip)})}"
        try:
            with build_opener(ProxyHandler({})).open(url, timeout=DGeoIp.TIMEOUT) as response:
                payload = json.load(response)
        except (URLError, OSError, HTTPException, ValueError) as error:
            raise GeoIpUnavailable("BMGeoIP lookup failed.") from error
        try:
            if (not isinstance(payload, dict) or payload.get("ip") != str(ip)
                    or type(payload.get("ip_version")) is not int or payload["ip_version"] != ip.version
                    or not isinstance(payload.get("results"), list)):
                raise ValueError("Invalid lookup response.")
            matches = []
            for row in payload["results"]:
                if (not isinstance(row, dict) or row.keys() != set(DGeoIp.COLUMNS)
                        or any(not isinstance(value, str) for value in row.values())):
                    raise ValueError("Invalid provider record.")
                start, end = ip_address(row["start_ip"]), ip_address(row["end_ip"])
                if (row["ip_version"] != str(ip.version) or start.version != ip.version
                        or end.version != ip.version or not int(start) <= int(ip) <= int(end)):
                    raise ValueError("Invalid provider range.")
                matches.append((-int(start), int(end), self._location(row)))
            if not matches:
                return GeoLocation()
            # Preserve the previous database lookup's start DESC, end ASC ordering.
            return min(matches, key=lambda match: match[:2])[2]
        except ValueError as error:
            raise GeoIpUnavailable("Invalid BMGeoIP response.") from error

    @staticmethod
    def _location(row: dict[str, str]) -> GeoLocation:
        for field, limit in (("country", DGeoIp.COUNTRY_NAME_LENGTH),
                             ("state", DGeoIp.REGION_NAME_LENGTH), ("city", DMyCount.CITY_NAME_LENGTH),
                             ("zip", DGeoIp.ZIP_LENGTH), ("timezone", DGeoIp.TIMEZONE_LENGTH)):
            if len(row[field]) > limit:
                raise ValueError(f"Invalid provider {field}.")
        country = row["country_code"] or None
        if country is not None and (len(country) != 2 or not country.isascii()):
            raise ValueError("Invalid provider country code.")
        coordinates = []
        for field, limit in (("latitude", 90), ("longitude", 180)):
            value = float(row[field]) if row[field].strip() else None
            if value is not None and not -limit <= value <= limit:
                raise ValueError(f"Invalid provider {field}.")
            coordinates.append(value)
        return GeoLocation(country_code=country, country_name=row["country"] or None,
                           region_name=row["state"] or None, city_name=row["city"] or None,
                           latitude=coordinates[0], longitude=coordinates[1],
                           zip=row["zip"] or None, timezone=row["timezone"] or None)

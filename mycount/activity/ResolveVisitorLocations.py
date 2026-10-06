"""Prepare map markers, preserving original visit snapshots and counts."""

from mycount.interface.CityLocations import CityLocations


class ResolveVisitorLocations:
    def __init__(self, cities: CityLocations) -> None:
        self._cities = cities

    def resolve(self, locations: list[dict[str, object]]) -> list[dict[str, object]]:
        mapped = []
        missing = []
        for row in locations:
            if row["latitude"] is not None and row["longitude"] is not None:
                mapped.append({**row, "coordinate_source": "GeoIP"})
            elif row["city_name"] and row["city_name"].strip():
                missing.append(row)
        for row, coordinates in zip(missing, self._cities.locate(missing)):
            if coordinates is not None:
                mapped.append({**row, "latitude": coordinates[0], "longitude": coordinates[1],
                               "coordinate_source": "CityDB"})
        markers = {}
        for row in mapped:
            key = tuple(row[field] for field in ("latitude", "longitude", "country_code",
                                                "region_name", "city_name", "coordinate_source"))
            if key in markers:
                markers[key]["page_views"] += row["page_views"]
            else:
                markers[key] = row
        return list(markers.values())

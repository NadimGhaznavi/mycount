"""Verify GeoNames publication, exact location matching, and snapshot preservation."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from mycount.activity.RefreshCities import RefreshCities
from mycount.activity.ResolveVisitorLocations import ResolveVisitorLocations
from mycount.interface.CityLocations import CityLocations
from mycount.interface.CitySchedule import CitySchedule


def city(city_id, name, country, region, latitude, longitude, aliases=''):
    return '\t'.join(map(str, (city_id, name, name, aliases, latitude, longitude,
                               'P', 'PPL', country, '', region, '', '', '', 1000, '', '', 'UTC', '2026-01-01')))


def fixture(directory, rows=None):
    (directory / 'admin1CodesASCII.txt').write_text('CA.08\tOntario\tOntario\t1\nUS.IL\tIllinois\tIllinois\t2\nUS.MA\tMassachusetts\tMassachusetts\t3\n')
    if rows is None:
        rows = [city(1, 'Toronto', 'CA', '08', 43.65, -79.38, 'Torontó'),
                city(2, 'Springfield', 'US', 'IL', 39.78, -89.65),
                city(3, 'Springfield', 'US', 'MA', 42.1, -72.59),
                city(4, 'Origin', 'CA', '08', 0, 0)]
    with ZipFile(directory / 'cities500.zip', 'w') as archive:
        archive.writestr('cities500.txt', '\n'.join(rows) + '\n')


def location(name, country='CA', region='Ontario', **changes):
    return {**dict(city_name=name, country_code=country, country_name=None, region_name=region,
                   latitude=None, longitude=None, page_views=3), **changes}


class CityLocationsTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cities = CityLocations(self.root)
        self.schedule = CitySchedule(self.root)
        self.source = Mock()
        self.source.download.side_effect = fixture
        self.refresh = RefreshCities(self.cities, self.schedule, self.source)

    def test_refresh_and_matching_city_alias_country_region_and_ambiguity(self):
        self.assertFalse(self.cities.status()['available'])
        self.assertTrue(self.refresh.run())
        self.assertEqual(self.cities.status()['city_count'], 4)
        rows = [location(' TORONTO '), location('Torontó'), location('Toronto', region='ON'),
                location('Toronto', country=None, country_name='Canada'),
                location('Springfield', 'US', 'Illinois'), location('Springfield', 'US', 'MA'),
                location('Springfield', 'US', None), location('Toronto', 'US', None),
                location('Toronto', region='Massachusetts'), location('Missing'), location('Origin'),
                location('Toronto', country=None, country_name='Unknown country')]
        self.assertEqual(self.cities.locate(rows), [(43.65, -79.38)] * 4 +
                         [(39.78, -89.65), (42.1, -72.59), None, None, None, None, (0.0, 0.0), None])
        self.assertEqual(list(self.root.glob('.refresh-*')), [])

    def test_resolver_retains_stored_coordinates_and_original_visit_snapshots(self):
        self.refresh.run()
        rows = [location('Toronto'), {**location('Missing'), 'latitude': 0, 'longitude': 0},
                location('Springfield', 'US', None), location(None),
                {**location('Origin'), 'latitude': 80}]
        original = deepcopy(rows)
        mapped = ResolveVisitorLocations(self.cities).resolve(rows)
        self.assertEqual(rows, original)
        self.assertEqual(len(mapped), 3)
        self.assertEqual(mapped[0]['coordinate_source'], 'GeoIP')
        self.assertEqual((mapped[0]['latitude'], mapped[0]['longitude']), (0, 0))
        self.assertEqual(mapped[1]['coordinate_source'], 'CityDB')
        self.assertEqual((mapped[1]['latitude'], mapped[1]['longitude']), (43.65, -79.38))
        self.assertEqual((mapped[2]['latitude'], mapped[2]['longitude']), (0, 0))
        self.assertEqual(sum(row['page_views'] for row in mapped), 9)

    def test_missing_dataset_keeps_stored_markers_and_leaves_cities_unresolved(self):
        rows = [location('Toronto'), {**location('Origin'), 'latitude': 0, 'longitude': 0}]
        mapped = ResolveVisitorLocations(self.cities).resolve(rows)
        self.assertEqual(len(mapped), 1)
        self.assertEqual(mapped[0]['coordinate_source'], 'GeoIP')
        self.assertFalse(self.cities.path.exists())

    def test_partial_coordinate_groups_for_same_city_share_one_marker(self):
        self.refresh.run()
        rows = [location('Toronto'), {**location('Toronto'), 'latitude': 40},
                {**location('Toronto'), 'longitude': -80}]
        mapped = ResolveVisitorLocations(self.cities).resolve(rows)
        self.assertEqual(len(mapped), 1)
        self.assertEqual(mapped[0]['page_views'], 9)
        self.assertEqual((mapped[0]['latitude'], mapped[0]['longitude']), (43.65, -79.38))

    def test_download_invalid_data_and_publication_failures_preserve_current_file(self):
        self.refresh.run()
        previous = self.cities.path.read_bytes()
        for rows in ([city(1, 'Broken', 'CA', '08', 'nan', 0)], ['invalid'], []):
            self.source.download.side_effect = lambda staging: fixture(staging, rows)
            with self.assertRaises(ValueError):
                self.refresh.run()
            self.assertEqual(self.cities.path.read_bytes(), previous)
        self.source.download.side_effect = TimeoutError('offline')
        with self.assertRaises(TimeoutError):
            self.refresh.run()
        self.assertEqual(self.cities.path.read_bytes(), previous)
        self.source.download.side_effect = fixture
        with patch.object(self.cities, 'publish', side_effect=OSError('disk full')), self.assertRaises(OSError):
            self.refresh.run()
        self.assertEqual(self.cities.path.read_bytes(), previous)
        self.assertEqual(list(self.root.glob('.refresh-*')), [])

    def test_refresh_replaces_dataset_and_existing_reader_can_finish(self):
        self.refresh.run()
        with self.cities._open() as reader:
            self.source.download.side_effect = lambda staging: fixture(staging, [city(5, 'New City', 'CA', '08', 1, 2)])
            self.refresh.run()
            self.assertEqual(reader.execute('SELECT city_count FROM metadata').fetchone()[0], 4)
        reader.close()
        self.assertEqual(self.cities.status()['city_count'], 1)
        self.assertEqual(self.cities.locate([location('New City'), location('Toronto')]), [(1, 2), None])

    def test_scheduled_bootstrap_disabled_due_and_overlapping_runs(self):
        import fcntl
        self.schedule.update(False, '0 3 1 */3 *')
        self.assertFalse(self.refresh.run(scheduled=True))
        self.source.download.assert_not_called()
        self.schedule.update(True, '0 3 1 */3 *')
        self.assertTrue(self.refresh.run(scheduled=True))
        self.source.reset_mock()
        with patch.object(self.schedule, 'due', return_value=False):
            self.assertFalse(self.refresh.run(scheduled=True))
        self.source.download.assert_not_called()
        with (self.root / 'refresh.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            self.assertFalse(self.refresh.run())
        with patch.object(self.schedule, 'due', return_value=True):
            self.assertFalse(self.refresh.run(scheduled=True))
        self.source.download.assert_not_called()

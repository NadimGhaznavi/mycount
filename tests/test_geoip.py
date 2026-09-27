"""GeoIP source validation using small local archives."""

import csv
from contextlib import nullcontext
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from mycount.constants.DGeoIp import DGeoIp
from mycount.activity.UpdateGeoIp import UpdateGeoIp
from mycount.interface.GeoIpSource import GeoIpSource


def archive(path, version, rows, columns=DGeoIp.COLUMNS):
    data = StringIO(newline="")
    writer = csv.writer(data)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(column, "") for column in columns])
    with ZipFile(path, "w") as zipped:
        zipped.writestr(DGeoIp.MEMBER.format(version=version), data.getvalue())


class FixtureGeoIpSource(GeoIpSource):
    def __init__(self, fail_version=None, city="Example"):
        self.fail_version = fail_version
        self.city = city

    def download(self, version, destination):
        if version == self.fail_version:
            raise OSError("Simulated download failure")
        ranges = {
            4: [("8.8.8.0", "8.8.8.255", self.city)],
            6: [("2606:4700::", "2606:4700:ffff:ffff:ffff:ffff:ffff:ffff", self.city),
                ("2606:4700:10::", "2606:4700:10::ff", "Specific")],
        }
        archive(destination, version, [
            {"ip_version": str(version), "start_ip": start, "end_ip": end,
             "continent": "North America", "country_code": "CA", "country": "Canada", "state": "Ontario", "city": city,
             "latitude": "43.2557", "longitude": "-79.8711",
             "zip": "00123", "timezone": "America/Toronto"}
            for start, end, city in ranges[version]
        ])


class GeoIpProgressTests(unittest.TestCase):
    def test_reports_stages_and_batch_progress(self):
        database = Mock()
        database.refresh.return_value = nullcontext()
        with patch('mycount.activity.UpdateGeoIp.monotonic', side_effect=[0, 11, 11, 12, 23, 23]):
            with self.assertLogs('mycount.activity.UpdateGeoIp', level='INFO') as logs:
                counts = UpdateGeoIp(FixtureGeoIpSource(), database).run()
        self.assertEqual(counts, {4: 1, 6: 2})
        self.assertEqual(database.append.call_count, 2)
        output = '\n'.join(logs.output)
        self.assertIn('Downloading IPv4', output)
        self.assertIn('IPv4: imported 1 ranges', output)
        self.assertIn('IPv6: imported 2 ranges', output)
        self.assertIn('Publishing GeoIP datasets', output)

    def test_failed_download_does_not_report_publication(self):
        database = Mock()
        database.refresh.return_value = nullcontext()
        with self.assertLogs('mycount.activity.UpdateGeoIp', level='INFO') as logs:
            with self.assertRaises(OSError):
                UpdateGeoIp(FixtureGeoIpSource(fail_version=6), database).run()
        self.assertNotIn('Publishing GeoIP datasets', '\n'.join(logs.output))


class GeoIpSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "source.zip"

    def test_unicode_comma_and_long_city_survive(self):
        city = "É, " + "x" * 134
        FixtureGeoIpSource(city=city).download(4, self.path)
        rows = list(GeoIpSource().rows(self.path, 4))
        self.assertEqual(rows[0].location.city_name, city)
        self.assertEqual(rows[0].location.country_name, 'Canada')
        self.assertEqual(rows[0].location.zip, '00123')
        self.assertEqual(rows[0].location.timezone, 'America/Toronto')
        self.assertEqual(len(rows[0].start), 16)

    def test_ipv6_nested_ranges_are_accepted(self):
        FixtureGeoIpSource().download(6, self.path)
        rows = list(GeoIpSource().rows(self.path, 6))
        self.assertEqual(len(rows), 2)
        self.assertLess(rows[0].start, rows[1].start)
        self.assertGreater(rows[0].end, rows[1].end)

    def test_wrong_header_is_rejected(self):
        archive(self.path, 4, [], ("unexpected",))
        with self.assertRaisesRegex(ValueError, "header"):
            list(GeoIpSource().rows(self.path, 4))

    def test_coordinates_allow_missing_zero_and_boundaries(self):
        for latitude, longitude, expected in (
            ('', '', (None, None)), (' ', '0', (None, 0.0)),
            ('0', '', (0.0, None)), ('90', '-180', (90.0, -180.0)),
            ('-90', '180', (-90.0, 180.0)), ('43.2557', '-79.8711', (43.2557, -79.8711)),
        ):
            with self.subTest(latitude=latitude, longitude=longitude):
                archive(self.path, 4, [{'ip_version': '4', 'start_ip': '8.8.8.0',
                    'end_ip': '8.8.8.255', 'latitude': latitude, 'longitude': longitude}])
                location = next(GeoIpSource().rows(self.path, 4)).location
                self.assertEqual((location.latitude, location.longitude), expected)

    def test_invalid_coordinates_are_rejected(self):
        for field, values in (('latitude', ('91', '-91', 'nan', 'inf', 'text')),
                              ('longitude', ('181', '-181', 'NaN', '-inf', 'text'))):
            for value in values:
                with self.subTest(field=field, value=value):
                    archive(self.path, 4, [{'ip_version': '4', 'start_ip': '8.8.8.0',
                        'end_ip': '8.8.8.255', field: value}])
                    with self.assertRaisesRegex(ValueError, 'coordinate at line 2'):
                        list(GeoIpSource().rows(self.path, 4))

    def test_optional_zip_timezone_and_length_limits(self):
        base = {'ip_version': '4', 'start_ip': '8.8.8.0', 'end_ip': '8.8.8.255'}
        archive(self.path, 4, [base])
        location = next(GeoIpSource().rows(self.path, 4)).location
        self.assertIsNone(location.zip)
        self.assertIsNone(location.timezone)
        for field, limit in (('zip', DGeoIp.ZIP_LENGTH), ('timezone', DGeoIp.TIMEZONE_LENGTH)):
            with self.subTest(field=field):
                archive(self.path, 4, [{**base, field: 'x' * (limit + 1)}])
                with self.assertRaisesRegex(ValueError, 'location'):
                    list(GeoIpSource().rows(self.path, 4))

    def test_optional_country_name_and_invalid_length(self):
        for country in ('', 'x' * (DGeoIp.COUNTRY_NAME_LENGTH + 1)):
            archive(self.path, 4, [{'ip_version': '4', 'start_ip': '8.8.8.0',
                                   'end_ip': '8.8.8.255', 'country': country}])
            if country:
                with self.assertRaisesRegex(ValueError, 'location'):
                    list(GeoIpSource().rows(self.path, 4))
            else:
                self.assertIsNone(next(GeoIpSource().rows(self.path, 4)).location.country_name)

    def test_invalid_range_and_address_family_are_rejected(self):
        for version, start, end in (("6", "8.8.8.0", "8.8.8.255"),
                                    ("4", "8.8.8.255", "8.8.8.0"),
                                    ("4", "2606:4700::", "2606:4700::ff")):
            with self.subTest(version=version, start=start):
                archive(self.path, 4, [{"ip_version": version, "start_ip": start, "end_ip": end}])
                with self.assertRaisesRegex(ValueError, "range"):
                    list(GeoIpSource().rows(self.path, 4))

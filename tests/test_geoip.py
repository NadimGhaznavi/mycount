"""Verify BMGeoIP's external contract and MyCount location conversion."""

from copy import deepcopy
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
import json
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from mycount.constants.DGeoIp import DGeoIp
from mycount.entity.GeoLocation import GeoLocation
from mycount.interface.GeoIp import GeoIp
from mycount.interface.GeoIpUnavailable import GeoIpUnavailable


def record(**changes):
    return {**dict.fromkeys(DGeoIp.COLUMNS, ""), "ip_version": "4",
            "start_ip": "8.8.8.0", "end_ip": "8.8.8.255", "country_code": "CA",
            "country": "Canada", "state": "Ontario", "city": "É, Example",
            "latitude": "43.2557", "longitude": "-79.8711", "zip": "00123",
            "timezone": "America/Toronto", **changes}


class GeoIpTests(unittest.TestCase):
    def lookup(self, rows, address="8.8.8.8", **changes):
        normalized = "8.8.8.8" if address.startswith("::ffff:") else address
        payload = {"ip": normalized, "ip_version": 6 if ":" in normalized else 4, "results": rows, **changes}
        with patch("mycount.interface.GeoIp.build_opener") as opener:
            opener.return_value.open.return_value = StringIO(json.dumps(payload))
            result = GeoIp().locate(address)
            self.assertEqual(parse_qs(urlsplit(opener.return_value.open.call_args.args[0]).query),
                             {"ip": [normalized]})
            self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], DGeoIp.TIMEOUT)
            return result

    def test_location_mapping_and_mapped_ipv4(self):
        for address in ("8.8.8.8", "::ffff:8.8.8.8"):
            location = self.lookup([record()], address)
            self.assertEqual(location, GeoLocation("CA", "Canada", "Ontario", "É, Example",
                                                   43.2557, -79.8711, "00123", "America/Toronto"))

    def test_overlaps_follow_numeric_start_descending_end_ascending(self):
        broad = record(ip_version="6", start_ip="2606:4700::", end_ip="2606:4700:ffff:ffff:ffff:ffff:ffff:ffff")
        nested = record(ip_version="6", start_ip="2606:4700:10::", end_ip="2606:4700:10::ff", city="Specific")
        wider = {**nested, "end_ip": "2606:4700:10::ffff", "city": "Wider"}
        for rows in ([broad, wider, nested], [nested, broad, wider]):
            self.assertEqual(self.lookup(rows, "2606:4700:10::1").city_name, "Specific")
        self.assertEqual(self.lookup([broad], "2606:4700:10::100").city_name, "É, Example")
        for address in ("8.8.8.0", "8.8.8.255"):
            self.assertEqual(self.lookup([record()], address).country_name, "Canada")

    def test_empty_and_non_global_addresses(self):
        self.assertEqual(self.lookup([]), GeoLocation())
        with patch("mycount.interface.GeoIp.build_opener") as opener:
            for address in ("127.0.0.1", "::1", "192.168.0.1", "::ffff:192.168.0.1"):
                self.assertEqual(GeoIp().locate(address), GeoLocation())
            opener.assert_not_called()

    def test_optional_fields_and_coordinate_boundaries(self):
        empty = record(**dict.fromkeys(("country_code", "country", "state", "city", "zip", "timezone", "latitude", "longitude"), ""))
        self.assertEqual(self.lookup([empty]), GeoLocation())
        location = self.lookup([record(latitude="0", longitude="-180")])
        self.assertEqual((location.latitude, location.longitude), (0.0, -180.0))

    def test_invalid_external_records_and_envelopes(self):
        invalid = [record(latitude=value) for value in ("nan", "inf", "91", "text")]
        invalid += [record(longitude="181"), record(city="x" * 256), record(country_code="CAN"),
                    record(ip_version="6"), record(end_ip="8.8.7.255"), record(start_ip="8.8.8.9"),
                    record(zip=123), record(extra="unexpected")]
        missing = deepcopy(record()); missing.pop("source"); invalid.append(missing)
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(GeoIpUnavailable):
                self.lookup([row])
        for changes in ({"ip": "1.1.1.1"}, {"ip_version": True}, {"results": None}):
            with self.subTest(changes=changes), self.assertRaises(GeoIpUnavailable):
                self.lookup([], **changes)

    def test_transport_http_and_json_failures_preserve_cause(self):
        for error in (TimeoutError("timeout"), URLError("offline"), IncompleteRead(b'partial'),
                      HTTPError("url", 503, "unavailable", {}, None)):
            with patch("mycount.interface.GeoIp.build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(GeoIpUnavailable) as raised:
                    GeoIp().locate("8.8.8.8")
                self.assertIs(raised.exception.__cause__, error)
        with patch("mycount.interface.GeoIp.build_opener") as opener:
            opener.return_value.open.return_value = StringIO("not json")
            with self.assertRaises(GeoIpUnavailable):
                GeoIp().locate("8.8.8.8")

    def test_real_http_lookup_and_service_unavailability(self):
        paths = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                paths.append(self.path)
                status = 200 if len(paths) == 1 else 503
                body = json.dumps({"ip": "8.8.8.8", "ip_version": 4, "results": [record()]}).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=server.serve_forever); thread.start()
            try:
                with patch.object(DGeoIp, "HOST", "127.0.0.1"), patch.object(DGeoIp, "PORT", server.server_port):
                    self.assertEqual(GeoIp().locate("8.8.8.8").zip, "00123")
                    with self.assertRaises(GeoIpUnavailable):
                        GeoIp().locate("8.8.8.8")
                self.assertEqual(paths, ["/api/lookup?ip=8.8.8.8"] * 2)
            finally:
                server.shutdown(); thread.join()

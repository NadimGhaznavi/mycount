"""Verify the city reference download boundary without network requests."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mycount.constants.DCities import DCities
from mycount.interface.GeoNamesSource import GeoNamesSource


class GeoNamesSourceTests(unittest.TestCase):
    def test_downloads_both_reference_files_with_identification_and_timeout(self):
        with TemporaryDirectory() as temporary, patch('mycount.interface.GeoNamesSource.urlopen') as opener:
            opener.side_effect = [BytesIO(b'cities'), BytesIO(b'regions')]
            directory = Path(temporary)
            GeoNamesSource().download(directory)
            self.assertEqual((directory / 'cities500.zip').read_bytes(), b'cities')
            self.assertEqual((directory / 'admin1CodesASCII.txt').read_bytes(), b'regions')
            self.assertEqual([call.args[0].full_url for call in opener.call_args_list],
                             [DCities.SOURCE + 'cities500.zip', DCities.SOURCE + 'admin1CodesASCII.txt'])
            for call in opener.call_args_list:
                self.assertTrue(call.args[0].get_header('User-agent').startswith('MyCount/'))
                self.assertEqual(call.kwargs['timeout'], DCities.TIMEOUT)

    def test_download_size_and_transport_errors_propagate(self):
        with TemporaryDirectory() as temporary, patch('mycount.interface.GeoNamesSource.urlopen') as opener:
            directory = Path(temporary)
            opener.return_value = BytesIO(b'oversized')
            with patch.object(DCities, 'MAX_DOWNLOAD_BYTES', 3), self.assertRaises(ValueError):
                GeoNamesSource().download(directory)
            opener.side_effect = TimeoutError('offline')
            with self.assertRaises(TimeoutError):
                GeoNamesSource().download(directory)

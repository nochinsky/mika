"""Offline tests of the developer-only punctuation asset fetcher."""
import importlib.util
import io
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

spec = importlib.util.spec_from_file_location('fetch_punctuation', Path(__file__).resolve().parents[1] / 'scripts/fetch_punctuation.py')
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, data):
        self.data = data
    def open(self, url, timeout):
        assert url.startswith('https://') and timeout > 0
        return Response(self.data)


class Fetch(unittest.TestCase):
    def test_verified_cache_skips_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'asset').write_bytes(b'good')
            with patch.object(urllib.request, 'build_opener', side_effect=AssertionError('network')):
                self.assertEqual(fetcher.fetch(root, 'asset', ('https://example.test/a', 4, hashlib.sha256(b'good').hexdigest())), root / 'asset')

    def test_success_and_failures_are_transactional(self):
        for received in (b'good', b'bad!', b'too long', b''):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / 'asset'
                target.write_bytes(b'previous')
                args = (root, 'asset', ('https://example.test/a', 4, hashlib.sha256(b'good').hexdigest()))
                with patch.object(urllib.request, 'build_opener', return_value=Opener(received)):
                    if received == b'good':
                        self.assertEqual(fetcher.fetch(*args), target)
                        self.assertEqual(target.read_bytes(), b'good')
                    else:
                        with self.assertRaises(ValueError):
                            fetcher.fetch(*args)
                        self.assertEqual(target.read_bytes(), b'previous')
                self.assertEqual(list(root.iterdir()), [target])

    def test_non_https_and_redirect_downgrades_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for url in ('http://example.test/a', 'file:///tmp/a'):
                with self.assertRaises(ValueError):
                    fetcher.fetch(Path(directory), 'asset', (url, 1, 'unused'))
        handler = fetcher.HTTPSOnly()
        req = urllib.request.Request('https://example.test/a')
        for url in ('http://example.test/b', 'file:///tmp/a'):
            with self.assertRaises(ValueError):
                handler.redirect_request(req, None, 302, 'Found', {}, url)
        result = handler.redirect_request(req, None, 302, 'Found', {}, 'https://example.test/b')
        self.assertEqual(result.full_url, 'https://example.test/b')


if __name__ == '__main__':
    unittest.main(verbosity=2)

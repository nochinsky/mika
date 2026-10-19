"""Offline checks for the fixed speech asset fetcher and payload contract."""
import hashlib
import importlib.util
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fetch_speech_assets', ROOT / 'scripts/fetch_speech_assets.py')
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)
DATA = b'tiny offline GGUF fixture'
DIGEST = hashlib.sha256(DATA).hexdigest()
URL = 'https://example.invalid/fixed-revision/model.gguf'


class Response(io.BytesIO):
    status = 200


class SpeechAssets(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='Mika speech ü ')
        self.addCleanup(temporary.cleanup)
        self.stage = Path(temporary.name)
        self.cache = self.stage / 'downloads'
        self.cache.mkdir()
        self.destination = self.cache / assets.MODEL_FILE
        self.spec = (URL, len(DATA), DIGEST)
        # A test that inadvertently attempts a real download must fail.
        self.network = patch.object(assets.urllib.request, 'build_opener',
                                    side_effect=AssertionError('Network forbidden in unit tests')).start()
        self.addCleanup(patch.stopall)

    def download(self, data=DATA):
        self.network.side_effect = None
        self.network.return_value.open.return_value = Response(data)
        return self.network.return_value

    def test_header_and_fetcher_pin_same_immutable_asset(self):
        header = (ROOT / 'src/speech_asset.h').read_text()
        self.assertIn('#include <stdint.h>', header)
        self.assertIn('#define MIKA_VAD_FILE "' + assets.MODEL_FILE + '"', header)
        self.assertIn('#define MIKA_VAD_BYTES UINT64_C(' + str(assets.MODEL_BYTES) + ')', header)
        self.assertIn('#define MIKA_VAD_SHA256 "' + assets.MODEL_SHA256 + '"', header)
        self.assertRegex(assets.REVISION, r'^[0-9a-f]{40}$')
        self.assertIn('/resolve/' + assets.REVISION + '/', assets.MODEL_URL)
        self.assertIn(assets.REVISION, header)
        license_text = assets.LICENSE.read_text()
        self.assertIn(assets.REVISION, license_text)
        self.assertIn('Copyright (c) 2020-present Silero Team', license_text)
        self.assertIn('The weights were not retrained or', license_text)
        self.assertEqual(len(re.findall(r'#define MIKA_VAD_', header)), 3)

    def test_verified_cache_needs_no_network(self):
        self.destination.write_bytes(DATA)
        self.assertEqual(assets.fetch(self.cache, assets.MODEL_FILE, self.spec), self.destination)
        self.network.assert_not_called()

    def test_corrupt_or_truncated_cache_is_replaced_after_verification(self):
        for old in (DATA[:-1], b'x' * len(DATA)):
            with self.subTest(old=old):
                self.destination.write_bytes(old)
                opener = self.download()
                self.assertEqual(assets.fetch(self.cache, assets.MODEL_FILE, self.spec), self.destination)
                self.assertEqual(self.destination.read_bytes(), DATA)
                opener.open.assert_called_with(URL, timeout=30)
                self.assertEqual(list(self.cache.iterdir()), [self.destination])

    def test_atomic_publication_only_after_validation(self):
        self.download()
        replace = assets.os.replace
        def publish(source, target):
            self.assertTrue(assets.verified(source, len(DATA), DIGEST))
            self.assertFalse(target.exists())
            replace(source, target)
        with patch.object(assets.os, 'replace', side_effect=publish) as publish_mock:
            assets.fetch(self.cache, assets.MODEL_FILE, self.spec)
        publish_mock.assert_called_once()

    def test_failed_downloads_leave_no_partial_cache(self):
        for data in (DATA[:-1], b'x' * len(DATA), DATA + b'oversized'):
            with self.subTest(data=data):
                self.download(data)
                with self.assertRaises(ValueError):
                    assets.fetch(self.cache, assets.MODEL_FILE, self.spec)
                self.assertEqual(list(self.cache.iterdir()), [])

    def test_corrupt_cache_is_never_reused_on_network_failure(self):
        self.destination.write_bytes(b'corrupt')
        self.download().open.side_effect = TimeoutError('offline')
        with self.assertRaises(TimeoutError):
            assets.fetch(self.cache, assets.MODEL_FILE, self.spec)
        self.assertFalse(assets.verified(self.destination, len(DATA), DIGEST))
        self.assertEqual(list(self.cache.iterdir()), [self.destination])

    def test_interrupted_download_is_not_published(self):
        response = self.download().open.return_value
        with patch.object(response, 'read', side_effect=[DATA[:4], OSError('interrupted')]):
            with self.assertRaises(OSError):
                assets.fetch(self.cache, assets.MODEL_FILE, self.spec)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_non_200_and_deadline_are_rejected(self):
        self.download().open.return_value.status = 206
        with self.assertRaises(ValueError):
            assets.fetch(self.cache, assets.MODEL_FILE, self.spec)
        self.download()
        with patch.object(assets.time, 'monotonic', side_effect=[0, 121]):
            with self.assertRaises(TimeoutError):
                assets.fetch(self.cache, assets.MODEL_FILE, self.spec)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_non_https_urls_and_redirects_are_rejected(self):
        with self.assertRaises(ValueError):
            assets.fetch(self.cache, assets.MODEL_FILE, ('http://example.invalid/model', len(DATA), DIGEST))
        self.network.assert_not_called()
        with self.assertRaises(ValueError):
            assets.HTTPSOnly().redirect_request(urllib.request.Request(URL), None, 302,
                                                'Found', {}, 'http://example.invalid/model')

    def test_symlinked_cache_is_replaced_not_followed(self):
        target = self.stage / 'outside.gguf'
        target.write_bytes(DATA)
        try:
            self.destination.symlink_to(target)
        except (OSError, NotImplementedError) as error:
            self.skipTest('Host cannot create test symlinks: ' + str(error))
        self.assertFalse(assets.verified(self.destination, len(DATA), DIGEST))
        self.download()
        assets.fetch(self.cache, assets.MODEL_FILE, self.spec)
        self.assertFalse(self.destination.is_symlink())
        self.assertEqual(target.read_bytes(), DATA)

    def test_payload_has_only_model_and_combined_license(self):
        self.destination.write_bytes(DATA)
        payload = self.stage / 'payload'
        payload.mkdir()
        (payload / 'private.wav').write_bytes(b'must not ship')
        (payload / 'obsolete-directory').mkdir()
        with patch.multiple(assets, MODEL_BYTES=len(DATA), MODEL_SHA256=DIGEST):
            self.assertEqual(assets.prepare(self.stage), payload)
        self.assertEqual({item.name for item in payload.iterdir()}, {assets.MODEL_FILE, 'LICENSE.txt'})
        self.assertEqual((payload / assets.MODEL_FILE).read_bytes(), DATA)
        self.assertEqual((payload / 'LICENSE.txt').read_bytes(), assets.LICENSE.read_bytes())
        self.network.assert_not_called()

    def test_failed_preparation_does_not_publish_or_remove_old_payload(self):
        payload = self.stage / 'payload'
        payload.mkdir()
        (payload / 'old-marker').write_bytes(b'old')
        self.download(b'wrong')
        with self.assertRaises(ValueError):
            assets.prepare(self.stage)
        self.assertEqual({item.name for item in payload.iterdir()}, {'old-marker'})
        self.assertEqual(list(self.cache.iterdir()), [])
        self.assertEqual({item.name for item in self.stage.iterdir()}, {'downloads', 'payload'})


if __name__ == '__main__':
    unittest.main(verbosity=2)

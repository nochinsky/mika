"""Offline tests of the developer-only punctuation asset fetcher."""
import importlib.util
import io
from pathlib import Path
import hashlib
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import asset_io
spec = importlib.util.spec_from_file_location('fetch_punctuation', ROOT / 'scripts/fetch_punctuation.py')
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

    def test_quantized_cache_skips_network_and_python_packages(self):
        digest = hashlib.sha256(b'good').hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'model.int8.onnx'
            target.write_bytes(b'good')
            with patch.object(fetcher, 'QUANTIZED', (4, digest)), \
                 patch.object(fetcher, 'fetch', side_effect=AssertionError('network')), \
                 patch.object(fetcher, 'convert', side_effect=AssertionError('conversion')):
                self.assertEqual(fetcher.quantized_model(root), target)

    def test_quantization_is_verified_and_transactional(self):
        digest = hashlib.sha256(b'good').hexdigest()
        for received in (b'good', b'bad!', b'too long', None):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'original'
                source.write_bytes(b'original')
                target = root / 'model.int8.onnx'
                target.write_bytes(b'previous')
                def convert(original, destination):
                    self.assertEqual(original, source)
                    if received is None:
                        raise RuntimeError('conversion failed')
                    destination.write_bytes(received)
                with patch.object(fetcher, 'QUANTIZED', (4, digest)), \
                     patch.object(fetcher, 'fetch', return_value=source), \
                     patch.object(fetcher, 'convert', side_effect=convert):
                    if received == b'good':
                        self.assertEqual(fetcher.quantized_model(root), target)
                        self.assertEqual(target.read_bytes(), b'good')
                    else:
                        with self.assertRaises((RuntimeError, ValueError)):
                            fetcher.quantized_model(root)
                        self.assertEqual(target.read_bytes(), b'previous')
                self.assertEqual(set(root.iterdir()), {source, target})

    def test_fullstop_payload_does_not_deploy_sherpa_or_python(self):
        for _, _, _, libraries in fetcher.SDK.values():
            self.assertTrue(all('onnxruntime' in lib for lib in libraries))
            self.assertFalse(any('sherpa-onnx-c-api' in lib for lib in libraries))
        self.assertIn('sp.model', fetcher.ARTIFACTS)
        self.assertNotIn('bpe.vocab', fetcher.ARTIFACTS)

    def test_non_https_and_redirect_downgrades_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for url in ('http://example.test/a', 'file:///tmp/a'):
                with self.assertRaises(ValueError):
                    fetcher.fetch(Path(directory), 'asset', (url, 1, 'unused'))
        self.assertIs(fetcher.fetch, asset_io.fetch)
        self.assertIs(fetcher.payload_transaction, asset_io.payload_transaction)
        # Both preparers use the redirect implementation exercised by speech_assets.
        response = Response(b'never drain a redirect body')
        response.status = 302
        response.headers = {'Location': 'http://example.test/b'}
        with patch.object(response, 'read', side_effect=AssertionError('redirect body read')), \
                patch.object(urllib.request, 'build_opener') as build:
            build.return_value.open.return_value = response
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                fetcher.fetch(Path(directory), 'asset', ('https://example.test/a', 1, 'unused'))
        self.assertTrue(response.closed)

    def test_cli_uses_bounded_preparation(self):
        with patch.object(sys, 'argv', ['fetch_punctuation.py', '--stage', 'stage', '--platform', 'linux']), \
                patch.object(fetcher, 'prepare_bounded') as bounded, \
                patch.object(fetcher, 'prepare', side_effect=AssertionError('Must run in worker')):
            fetcher.main()
        bounded.assert_called_once_with(Path('stage'), 'linux')


class Preparation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='Mika formatter preparation ü ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage = self.root / 'stage'
        self.payload = self.stage / 'payload'
        self.payload.mkdir(parents=True)
        (self.payload / 'old-marker').write_bytes(b'previous payload')
        self.asset = self.root / 'fixture'
        self.asset.write_bytes(b'tiny fake asset')
        self.archive = self.root / 'runtime.tar.bz2'
        variant = fetcher.SDK['linux'][0]
        with tarfile.open(self.archive, 'w:bz2') as output:
            member = tarfile.TarInfo('sherpa-onnx-v' + fetcher.VERSION + '-' + variant + '/lib/libonnxruntime.so')
            member.size = 7
            output.addfile(member, io.BytesIO(b'runtime'))
        self.quantizer = patch.object(fetcher, 'quantized_model', return_value=self.asset).start()
        self.network = patch.object(fetcher, 'fetch', side_effect=lambda cache, name, spec:
                                    self.archive if name.endswith('.tar.bz2') else self.asset).start()
        self.addCleanup(patch.stopall)

    def test_complete_payload_replaces_previous_only_after_preparation(self):
        fetcher.prepare(self.stage, 'linux')
        self.assertEqual({p.name for p in self.payload.iterdir()},
                         {'model.int8.onnx', 'sp.model', 'libonnxruntime.so', 'licenses'})
        self.assertEqual((self.payload / 'libonnxruntime.so').read_bytes(), b'runtime')
        self.assertFalse(list(self.stage.glob('payload-*')))

    def test_failed_preparation_preserves_previous(self):
        self.network.side_effect = OSError('injected download failure')
        with self.assertRaises(OSError):
            fetcher.prepare(self.stage, 'linux')
        self.assertEqual((self.payload / 'old-marker').read_bytes(), b'previous payload')
        self.assertFalse(list(self.stage.glob('payload-*')))

    def test_failed_publication_restores_previous(self):
        rename = Path.rename
        def fail_publication(source, destination):
            if source.name == 'payload' and source.parent != self.stage:
                raise OSError('injected publication failure')
            return rename(source, destination)
        with patch.object(Path, 'rename', autospec=True, side_effect=fail_publication):
            with self.assertRaisesRegex(OSError, 'publication failure'):
                fetcher.prepare(self.stage, 'linux')
        self.assertEqual((self.payload / 'old-marker').read_bytes(), b'previous payload')
        self.assertFalse(list(self.stage.glob('payload-*')))

    def test_timeout_kills_and_reaps_conversion_worker(self):
        marker, late = self.root / 'entered', self.root / 'continued'
        worker = self.root / 'offline_worker.py'
        worker.write_text('''import sys, time
from pathlib import Path
sys.path.insert(0, %r)
import fetch_punctuation as assets
def convert(source, destination):
    Path(%r).write_text('entered')
    time.sleep(60)
    Path(%r).write_text('must not continue')
assets.convert = convert
assets.fetch = lambda *args: Path(%r)
assets.main()
''' % (str(ROOT / 'scripts'), str(marker), str(late), str(self.asset)), encoding='utf-8')
        processes = []
        popen = subprocess.Popen
        def start(*args, **kwargs):
            process = popen(*args, **kwargs)
            processes.append(process)
            return process
        started = time.monotonic()
        with patch.object(fetcher, '__file__', str(worker)), \
                patch.object(asset_io.subprocess, 'Popen', side_effect=start):
            with self.assertRaises(subprocess.TimeoutExpired):
                fetcher.prepare_bounded(self.stage, 'linux', timeout=2)
        self.assertLess(time.monotonic() - started, 7)
        self.assertTrue(marker.exists())
        self.assertFalse(late.exists())
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].returncode)
        self.assertEqual((self.payload / 'old-marker').read_bytes(), b'previous payload')


if __name__ == '__main__':
    unittest.main(verbosity=2)

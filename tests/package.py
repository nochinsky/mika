"""Offline archive-content checks with tiny fake binaries/data, no model/network."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class Package(unittest.TestCase):
    def build(self, platform, extra=None, missing=None):
        temporary = tempfile.TemporaryDirectory(prefix='Mika package ü ')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        stage = root / 'stage'
        binary = stage / 'bin'
        payload = binary / 'punctuation'
        (payload / 'licenses').mkdir(parents=True)
        (payload / 'licenses/NOTICE.txt').write_text('test notice')
        windows = platform == 'windows'
        (binary / ('mika.exe' if windows else 'mika')).write_bytes(b'app')
        (binary / 'mika-inference-test').write_bytes(b'must not ship')
        names = {'model.int8.onnx', 'sp.model'} | (
            {'mika-fullstop.dll', 'onnxruntime.dll', 'onnxruntime_providers_shared.dll'} if windows
            else {'libmika-fullstop.dylib', 'libonnxruntime.dylib'} if platform == 'macos'
            else {'libmika-fullstop.so', 'libonnxruntime.so'})
        for name in names - {missing}:
            (payload / name).write_bytes(b'test asset')
        if platform == 'linux':
            (stage / 'lib').mkdir()
            (stage / 'lib/libggml-cpu-test.so').write_bytes(b'test library')
        if extra:
            (payload / extra).write_bytes(b'must not ship')
        result = subprocess.run([sys.executable, ROOT / 'scripts/package.py', '--stage', stage,
                                 '--output', root / 'dist', '--platform', platform, '--version', 'vtest'],
                                capture_output=True, timeout=30)
        archive = root / 'dist' / ('mika-windows-x86_64.zip' if windows else
                                   'mika-macos-arm64.tar.gz' if platform == 'macos' else 'mika-linux-x86_64.tar.gz')
        return result, archive

    def test_payload_and_notices_but_no_validation_probe(self):
        for platform in ('linux', 'windows', 'macos'):
            result, archive = self.build(platform)
            self.assertEqual(result.returncode, 0, result.stderr)
            if platform != 'windows':
                with tarfile.open(archive) as bundle:
                    names = bundle.getnames()
            else:
                with zipfile.ZipFile(archive) as bundle:
                    names = bundle.namelist()
            self.assertIn('mika/bin/punctuation/model.int8.onnx', names)
            self.assertIn('mika/bin/punctuation/licenses/NOTICE.txt', names)
            self.assertFalse(any('inference-test' in name or name.endswith('.gguf') for name in names))
            self.assertEqual(Path(str(archive) + '.sha256').read_text().split()[0],
                             hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_incomplete_payload_is_rejected(self):
        for platform in ('linux', 'windows', 'macos'):
            result, archive = self.build(platform, missing='sp.model')
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(archive.exists())

    def test_unexpected_data_or_private_audio_is_rejected(self):
        for name in ('recording.wav', 'fullstop.fp32.onnx', 'licenses/recording.wav'):
            result, archive = self.build('linux', extra=name)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(archive.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)

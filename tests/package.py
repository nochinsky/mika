"""Offline archive-content checks with tiny fake binaries/data, no model/network."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class Package(unittest.TestCase):
    def build(self, platform, extra=None, missing=None, change_speech=None, change_punctuation=None):
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
        (binary / 'granite-speech.gguf').write_bytes(b'downloaded ASR must not ship')
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
        speech = binary / 'speech'
        speech.mkdir()
        (speech / 'silero-vad-v6.2-F32.gguf').write_bytes(b'tiny fake VAD')
        (speech / 'LICENSE.txt').write_text('test Silero notice')
        if change_speech:
            change_speech(speech)
        if change_punctuation:
            change_punctuation(payload)
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
                    version = bundle.extractfile('mika/VERSION').read()
            else:
                with zipfile.ZipFile(archive) as bundle:
                    names = bundle.namelist()
                    version = bundle.read('mika/VERSION')
            self.assertEqual(version, b'vtest\n')
            self.assertIn('mika/bin/punctuation/model.int8.onnx', names)
            self.assertIn('mika/bin/punctuation/licenses/NOTICE.txt', names)
            self.assertIn('mika/bin/speech/LICENSE.txt', names)
            self.assertEqual([name for name in names if name.endswith('.gguf')],
                             ['mika/bin/speech/silero-vad-v6.2-F32.gguf'])
            self.assertFalse(any('inference-test' in name for name in names))
            if platform == 'linux':
                self.assertIn('mika/lib/libggml-cpu-test.so', names)
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

    def test_linked_formatter_payload_members_and_notices_are_rejected(self):
        for platform in ('linux', 'windows', 'macos'):
            for name in (None, 'model.int8.onnx', 'sp.model', 'licenses', 'licenses/NOTICE.txt'):
                with self.subTest(platform=platform, name=name):
                    def change(payload):
                        item = payload / name if name else payload
                        target = payload.parent / ('linked-' + (name or 'payload').replace('/', '-'))
                        item.rename(target)
                        try:
                            os.symlink(target, item, target_is_directory=target.is_dir())
                        except (OSError, NotImplementedError) as error:
                            self.skipTest('Host cannot create test symlinks: ' + str(error))
                    result, archive = self.build(platform, change_punctuation=change)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(archive.exists())

    def test_unexpected_formatter_special_entries_are_rejected(self):
        def change(payload):
            try:
                (payload / 'unexpected').symlink_to(payload / 'missing')
            except (OSError, NotImplementedError) as error:
                self.skipTest(str(error))
        result, archive = self.build('linux', change_punctuation=change)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(archive.exists())

    def test_missing_speech_assets_are_rejected(self):
        for platform in ('linux', 'windows', 'macos'):
            for name in ('silero-vad-v6.2-F32.gguf', 'LICENSE.txt'):
                with self.subTest(platform=platform, name=name):
                    result, archive = self.build(
                        platform, change_speech=lambda speech: (speech / name).unlink())
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(archive.exists())
            result, archive = self.build(
                platform, change_speech=lambda speech: shutil.rmtree(speech))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(archive.exists())

    def test_extra_speech_files_or_directories_are_rejected(self):
        for platform in ('linux', 'windows', 'macos'):
            for name in ('recording.wav', 'granite-speech.gguf', '.private', 'extra'):
                with self.subTest(platform=platform, name=name):
                    def change(speech):
                        if name == 'extra':
                            (speech / name).mkdir()
                        else:
                            (speech / name).write_bytes(b'must not ship')
                    result, archive = self.build(platform, change_speech=change)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(archive.exists())

    def test_linked_speech_payload_or_members_are_rejected(self):
        for platform in ('linux', 'windows', 'macos'):
            for name in (None, 'silero-vad-v6.2-F32.gguf', 'LICENSE.txt'):
                with self.subTest(platform=platform, name=name):
                    def change(speech):
                        item = speech / name if name else speech
                        target = speech.parent / ('linked-' + (name or 'speech'))
                        item.rename(target)
                        try:
                            os.symlink(target, item, target_is_directory=name is None)
                        except (OSError, NotImplementedError) as error:
                            self.skipTest('Host cannot create test symlinks: ' + str(error))
                    result, archive = self.build(platform, change_speech=change)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(archive.exists())

    def test_directory_in_place_of_speech_file_is_rejected(self):
        def change(speech):
            (speech / 'LICENSE.txt').unlink()
            (speech / 'LICENSE.txt').mkdir()
        result, archive = self.build('linux', change_speech=change)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(archive.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)

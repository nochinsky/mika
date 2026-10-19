"""Offline release-gate fixtures: no network, executable payloads or recordings."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('release_assets', ROOT / 'scripts/check_release_assets.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseAssets(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='Mika release ü ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in release.ARCHIVES:
            self.archive(name)

    def archive(self, name, version='v0.3.0\n', duplicate=False):
        path = self.root / name
        data = version.encode('ascii')
        if name.endswith('.zip'):
            with zipfile.ZipFile(path, 'w') as output:
                output.writestr('mika/VERSION', data)
        else:
            with tarfile.open(path, 'w:gz') as output:
                for _ in range(2 if duplicate else 1):
                    member = tarfile.TarInfo('mika/VERSION')
                    member.size = len(data)
                    output.addfile(member, io.BytesIO(data))
        self.checksum(name)

    def checksum(self, name):
        digest = hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        (self.root / (name + '.sha256')).write_text(digest + '  ' + name + '\n', encoding='ascii')

    def test_complete_three_platform_release(self):
        self.assertEqual(set(release.validate(self.root, 'v0.3.0')), set(release.ARCHIVES))

    def test_native_windows_crlf_metadata_is_accepted(self):
        for name in release.ARCHIVES:
            self.archive(name, 'v0.3.0\r\n')
        self.assertEqual(set(release.validate(self.root, 'v0.3.0')), set(release.ARCHIVES))

    def test_missing_mac_or_extra_payload_blocks_publication(self):
        for name in ('mika-macos-arm64.tar.gz', 'mika-macos-arm64.tar.gz.sha256'):
            path = self.root / name
            data = path.read_bytes()
            path.unlink()
            with self.assertRaises(ValueError):
                release.validate(self.root, 'v0.3.0')
            path.write_bytes(data)
        (self.root / 'private.wav').write_bytes(b'not allowed')
        with self.assertRaises(ValueError):
            release.validate(self.root, 'v0.3.0')

    def test_corruption_and_wrong_checksum_filename(self):
        name = release.ARCHIVES[0]
        (self.root / name).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            release.validate(self.root, 'v0.3.0')
        self.archive(name)
        checksum = self.root / (name + '.sha256')
        checksum.write_text(checksum.read_text(encoding='ascii').replace(name, 'wrong.tar.gz'), encoding='ascii')
        with self.assertRaises(ValueError):
            release.validate(self.root, 'v0.3.0')

    def test_mixed_versions_duplicate_and_oversize_version_rejected(self):
        for name in release.ARCHIVES:
            for version in ('v0.2.0\n', 'v0.2.0\r\n', 'v0.3.0', 'v0.3.0\r',
                            'v0.3.0\r\n\r\n', 'v0.3.0 \r\n', 'x' * 129):
                self.archive(name, version)
                with self.assertRaises(ValueError):
                    release.validate(self.root, 'v0.3.0')
            self.archive(name)
        self.archive(release.ARCHIVES[0], duplicate=True)
        with self.assertRaises(ValueError):
            release.validate(self.root, 'v0.3.0')

    def test_linked_assets_rejected(self):
        name = release.ARCHIVES[0]
        path = self.root / name
        outside = self.root.parent / (self.root.name + '-archive')
        outside.write_bytes(path.read_bytes())
        self.addCleanup(outside.unlink)
        path.unlink()
        try:
            path.symlink_to(outside)
        except (OSError, NotImplementedError) as error:
            self.skipTest(str(error))
        with self.assertRaises(ValueError):
            release.validate(self.root, 'v0.3.0')


if __name__ == '__main__':
    unittest.main(verbosity=2)

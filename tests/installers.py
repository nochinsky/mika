"""Linux installer transaction tests; private HOME, offline fixture, no real install."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

INSTALLER = str(Path(sys.argv[1]).resolve())
sys.argv = sys.argv[:1]


@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid() != 0, 'requires a normal Linux user')
class Installer(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='mika installer test ')
        self.addCleanup(self.scratch.cleanup)
        self.home = Path(self.scratch.name) / 'home'
        self.home.mkdir()
        self.data = self.home / 'data'
        self.root = self.data / 'mika' / 'app'
        self.archive = Path(self.scratch.name) / 'release.tar.gz'
        self.env = {**os.environ, 'HOME': str(self.home), 'XDG_DATA_HOME': str(self.data),
                    'SHELL': '/bin/bash', 'MIKA_ARCHIVE_PATH': str(self.archive), 'MIKA_VERSION': 'latest'}
        self.package('1.2.3')

    def package(self, version, fail_after_move=False):
        source = Path(self.scratch.name) / 'package' / 'mika'
        (source / 'bin').mkdir(parents=True, exist_ok=True)
        (source / 'VERSION').write_text(version + '\n')
        program = source / 'bin' / 'mika'
        body = '#!/bin/sh\n'
        if fail_after_move:
            body += 'case "$0" in */app/bin/mika) exit 42;; esac\n'
        program.write_text(body + f"printf 'mika {version}\\n'\n")
        program.chmod(0o755)
        with tarfile.open(self.archive, 'w:gz') as archive:
            archive.add(source, arcname='mika')
        self.checksum()

    def checksum(self):
        Path(str(self.archive) + '.sha256').write_text(hashlib.sha256(self.archive.read_bytes()).hexdigest() + '  release.tar.gz\n')

    def install(self, success=True):
        result = subprocess.run(['bash', INSTALLER], env=self.env, capture_output=True, timeout=15)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        self.assertEqual(list((self.data / 'mika').glob('.install.*')), [])
        return result

    def test_install_and_reinstall_preserve_model_and_deduplicate_path(self):
        models = self.data / 'mika' / 'models'
        models.mkdir(parents=True)
        (models / 'keep.gguf').write_bytes(b'existing model')
        self.install()
        self.install()
        self.assertTrue((self.home / '.local/bin/mika').is_symlink())
        self.assertEqual(subprocess.check_output([self.home / '.local/bin/mika', '--version']), b'mika 1.2.3\n')
        self.assertEqual((models / 'keep.gguf').read_bytes(), b'existing model')
        self.assertEqual((self.home / '.bashrc').read_text().count('# >>> Mika CLI >>>'), 1)

    def test_checksum_failure_leaves_installed_version_unchanged(self):
        self.install()
        self.package('1.2.4')
        Path(str(self.archive) + '.sha256').write_text('0' * 64 + '  release.tar.gz\n')
        self.install(success=False)
        self.assertEqual((self.root / 'VERSION').read_text(), '1.2.3\n')

    def test_post_install_failure_rolls_back(self):
        self.install()
        self.package('1.2.4', fail_after_move=True)
        self.install(success=False)
        self.assertEqual((self.root / 'VERSION').read_text(), '1.2.3\n')
        self.assertEqual(subprocess.check_output([self.home / '.local/bin/mika', '--version']), b'mika 1.2.3\n')

    def test_does_not_overwrite_an_unrelated_command(self):
        command = self.home / '.local/bin/mika'
        command.parent.mkdir(parents=True)
        command.write_text('unrelated')
        result = subprocess.run(['bash', INSTALLER], env=self.env, capture_output=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(command.read_text(), 'unrelated')
        self.assertFalse(self.root.exists())

    def test_rejects_archive_traversal(self):
        with tarfile.open(self.archive, 'w:gz') as archive:
            info = tarfile.TarInfo('../escape')
            info.size = 0
            archive.addfile(info)
        self.checksum()
        self.install(success=False)
        self.assertFalse(self.root.exists())
        self.assertFalse((self.data / 'mika/escape').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)

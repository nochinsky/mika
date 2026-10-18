"""Offline Mac install/remove transactions in private homes, no real install/audio.

On Darwin these run stock /bin/bash and BSD tools. Linux runs explicitly mocked
OS/BSD commands as logic checks only; those are not native macOS validation.
"""
import fcntl
import hashlib
import os
from pathlib import Path
import pty
import select
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'granite-speech-5.0-470m-turboctc-Q4_K_M.gguf'


@unittest.skipUnless(os.name == 'posix' and os.geteuid() != 0, 'normal POSIX user required')
class MacScripts(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='Mika Mac scripts ü ')
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.home = self.scratch / 'home'
        self.home.mkdir()
        self.parent = self.home / 'Library/Application Support/Mika'
        self.app = self.parent / 'app'
        self.models = self.parent / 'models'
        self.command = self.home / '.local/bin/mika'
        self.archive = self.scratch / 'release.tar.gz'
        self.env = {**os.environ, 'HOME': str(self.home), 'SHELL': '/bin/zsh', 'ZDOTDIR': str(self.home),
                    'XDG_CONFIG_HOME': str(self.home / '.config'), 'MIKA_ARCHIVE_PATH': str(self.archive),
                    'MIKA_UNINSTALL_YES': '1', 'MIKA_KEEP_MODEL': '0', 'MIKA_REINSTALL': '0', 'MIKA_VERSION': 'latest'}
        if sys.platform != 'darwin':
            tools = self.scratch / 'mock-native-tools'
            tools.mkdir()
            definitions = {
                'uname': '#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo arm64;; esac\n',
                'sw_vers': '#!/bin/sh\necho 14.0\n',
                'lsof': f'#!{sys.executable}\nimport os,sys\nsys.exit(0 if sys.argv[-1] == os.environ.get("MIKA_TEST_ACTIVE") else 1)\n',
                'stat': f'#!{sys.executable}\nimport os,stat,sys\nprint(oct(stat.S_IMODE(os.stat(sys.argv[-1]).st_mode))[2:])\n',
            }
            for name, text in definitions.items():
                (tools / name).write_text(text)
                (tools / name).chmod(0o755)
            self.env['PATH'] = str(tools) + os.pathsep + os.environ['PATH']
        self.package('1.2.3')

    def package(self, version, fail_final=False):
        source = self.scratch / 'package/mika'
        (source / 'bin').mkdir(parents=True, exist_ok=True)
        (source / 'VERSION').write_text('v' + version + '\n')
        body = '#!/bin/sh\n'
        if fail_final:
            body += 'case "$0" in */app/bin/mika) exit 42;; esac\n'
        program = source / 'bin/mika'
        program.write_text(body + f'printf "mika {version}\\n"\n')
        program.chmod(0o755)
        with tarfile.open(self.archive, 'w:gz') as archive:
            archive.add(source, arcname='mika')
        self.checksum()

    def checksum(self):
        Path(str(self.archive) + '.sha256').write_text(hashlib.sha256(self.archive.read_bytes()).hexdigest() + '  archive\n')

    def run_script(self, name, success=True, extra_env=None):
        result = subprocess.run(['/bin/bash', ROOT / name], env={**self.env, **(extra_env or {})},
                                capture_output=True, timeout=30, start_new_session=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def install(self, **kwargs):
        return self.run_script('install-macos.sh', **kwargs)

    def remove(self, **kwargs):
        return self.run_script('uninstall-macos.sh', **kwargs)

    def model(self):
        self.models.mkdir(parents=True, exist_ok=True)
        (self.models / MODEL).write_bytes(b'fake model')
        (self.models / (MODEL + '.part.test')).write_bytes(b'partial')
        (self.models / '.download.lock').touch()

    def test_install_remove_repeat_preserves_shell_content_and_mode(self):
        profile = self.home / '.zshrc'
        profile.write_text('export USER_SETTING=keep\n')
        profile.chmod(0o640)
        self.install()
        self.model()
        self.assertEqual(subprocess.check_output([self.command, '--version']), b'mika 1.2.3\n')
        self.remove()
        self.assertFalse(self.parent.exists())
        self.assertFalse(self.command.is_symlink())
        self.assertEqual(profile.read_text(), 'export USER_SETTING=keep\n\n')
        self.assertEqual(profile.stat().st_mode & 0o777, 0o640)
        self.remove()
        self.assertFalse(self.parent.exists())

    def test_empty_remove_creates_no_directories(self):
        self.remove()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_keep_model_then_full_remove(self):
        self.install()
        self.model()
        self.remove(extra_env={'MIKA_KEEP_MODEL': '1'})
        self.assertFalse(self.app.exists())
        self.assertTrue((self.models / MODEL).exists())
        self.remove()
        self.assertFalse(self.parent.exists())

    def test_update_noop_and_command_repair(self):
        self.install()
        self.command.unlink()
        self.archive.unlink()
        self.assertIn(b'already up to date', self.install().stdout)
        self.assertTrue(self.command.is_symlink())
        self.package('1.2.4')
        self.install()
        self.assertEqual(subprocess.check_output([self.command, '--version']), b'mika 1.2.4\n')
        self.assertEqual((self.home / '.zshrc').read_text().count('# >>> Mika CLI >>>'), 1)

    def test_bad_checksum_preserves_app_and_model(self):
        self.install()
        self.model()
        self.package('1.2.4')
        Path(str(self.archive) + '.sha256').write_text('0' * 64 + '  archive\n')
        self.install(success=False)
        self.assertEqual((self.app / 'VERSION').read_text(), 'v1.2.3\n')
        self.assertTrue((self.models / MODEL).exists())
        self.assertFalse((self.parent / '.maintenance-lock').exists())

    def test_post_move_failure_rolls_back(self):
        self.install()
        self.package('1.2.4', fail_final=True)
        self.install(success=False)
        self.assertEqual(subprocess.check_output([self.command, '--version']), b'mika 1.2.3\n')
        self.assertFalse(list(self.parent.glob('.install.*')))

    def test_archive_paths_links_and_special_files_rejected(self):
        self.install()
        for name, kind in [('../escape', tarfile.REGTYPE), ('mika/link', tarfile.SYMTYPE),
                           ('mika/hardlink', tarfile.LNKTYPE), ('mika/pipe', tarfile.FIFOTYPE)]:
            with tarfile.open(self.archive, 'w:gz') as archive:
                item = tarfile.TarInfo(name)
                item.type = kind
                item.linkname = '/tmp/outside'
                archive.addfile(item)
            self.checksum()
            self.install(success=False)
            self.assertEqual((self.app / 'VERSION').read_text(), 'v1.2.3\n')

    def test_maintenance_lock_blocks_install_and_remove(self):
        self.install()
        lock = self.parent / '.maintenance-lock'
        lock.mkdir()
        self.install(success=False)
        self.remove(success=False)
        self.assertTrue(lock.exists())
        self.assertTrue(self.app.exists())

    def test_active_download_blocks_removal(self):
        self.install()
        self.model()
        model = self.models / MODEL
        with model.open('rb'):
            self.remove(success=False, extra_env={'MIKA_TEST_ACTIVE': str(model)})
        self.assertTrue(self.app.exists())

    def test_modified_setup_unknown_data_and_unrelated_command_survive(self):
        self.install()
        self.model()
        self.command.unlink()
        self.command.write_text('unrelated command')
        profile = self.home / '.zshrc'
        profile.write_text(profile.read_text().replace('case ":$PATH:"', 'case ":$MY_PATH:"'))
        before = profile.read_bytes()
        notes = self.models / 'notes.txt'
        notes.write_text('private notes')
        self.remove()
        self.assertEqual(notes.read_text(), 'private notes')
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(self.command.read_text(), 'unrelated command')

    def test_ownership_and_linked_roots_refused(self):
        self.install()
        marker = self.app / 'ARCHIVE_SHA256'
        contents = marker.read_bytes()
        marker.unlink()
        self.remove(success=False)
        marker.write_bytes(contents)
        outside = self.scratch / 'outside'
        self.app.rename(outside)
        self.app.symlink_to(outside, target_is_directory=True)
        self.remove(success=False)
        self.assertTrue((outside / 'VERSION').exists())

    def test_fish_cleanup_and_nested_symlink_safety(self):
        self.env['SHELL'] = '/bin/fish'
        self.install()
        outside = self.scratch / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('safe')
        (self.app / 'linked').symlink_to(outside, target_is_directory=True)
        self.remove()
        self.assertEqual((outside / 'keep').read_text(), 'safe')
        self.assertFalse((self.home / '.config/fish/conf.d/mika.fish').exists())

    def test_piped_input_cannot_confirm_without_terminal(self):
        self.install()
        result = subprocess.run(['/bin/bash'], input=(ROOT / 'uninstall-macos.sh').read_bytes() + b'\ny\n',
                                env={**self.env, 'MIKA_UNINSTALL_YES': '0'}, start_new_session=True,
                                capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.app.exists())

    def test_terminal_decline_leaves_install_unchanged(self):
        self.install()
        master, slave = pty.openpty()
        def session():
            os.setsid()
            signal.signal(signal.SIGTTOU, signal.SIG_IGN)
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            os.tcsetpgrp(slave, os.getpgrp())
            signal.signal(signal.SIGTTOU, signal.SIG_DFL)
        process = subprocess.Popen(['/bin/bash'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=slave,
                                   env={**self.env, 'MIKA_UNINSTALL_YES': '0'}, preexec_fn=session)
        try:
            process.stdin.write((ROOT / 'uninstall-macos.sh').read_bytes())
            process.stdin.close()
            process.stdin = None
            messages = bytearray()
            deadline = time.monotonic() + 20
            while b'Remove Mika? [y/N]' not in messages:
                if time.monotonic() > deadline:
                    self.fail(repr(messages))
                if select.select([master], [], [], .1)[0]:
                    messages.extend(os.read(master, 4096))
            os.write(master, b'n\n')
            process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130)
            self.assertTrue(self.app.exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    if sys.platform == 'darwin':
        import faulthandler
        faulthandler.dump_traceback_later(60, repeat=True)
    unittest.main(verbosity=2, failfast=True)

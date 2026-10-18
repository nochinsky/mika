"""Offline Linux removal tests: temporary homes only, never the user's Mika."""
import fcntl
import hashlib
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'uninstall.sh'
MODEL = 'granite-speech-5.0-470m-turboctc-Q4_K_M.gguf'


@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid() != 0, 'normal Linux user required')
class Uninstallers(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='Mika removal ü ')
        self.addCleanup(temporary.cleanup)
        self.scratch = Path(temporary.name)
        self.home = self.scratch / 'home'
        self.home.mkdir()
        self.data = self.home / 'data'
        self.parent = self.data / 'mika'
        self.app = self.parent / 'app'
        self.models = self.parent / 'models'
        self.command = self.home / '.local/bin/mika'
        self.env = {**os.environ, 'HOME': str(self.home), 'XDG_DATA_HOME': str(self.data),
                    'XDG_CONFIG_HOME': str(self.home / '.config'), 'ZDOTDIR': str(self.home),
                    'SHELL': '/bin/bash', 'MIKA_KEEP_MODEL': '0', 'MIKA_UNINSTALL_YES': '1'}
        source = self.scratch / 'package/mika'
        (source / 'bin').mkdir(parents=True)
        (source / 'VERSION').write_text('vtest\n')
        program = source / 'bin/mika'
        program.write_text('#!/bin/sh\nprintf "mika test\\n"\n')
        program.chmod(0o755)
        archive = self.scratch / 'release.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            bundle.add(source, arcname='mika')
        Path(str(archive) + '.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  release.tar.gz\n')
        self.env['MIKA_ARCHIVE_PATH'] = str(archive)
        self.env['MIKA_VERSION'] = 'latest'

    def install(self):
        result = subprocess.run(['bash', ROOT / 'install.sh'], env=self.env, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def model(self):
        self.models.mkdir(parents=True, exist_ok=True)
        (self.models / MODEL).write_bytes(b'fake model')
        (self.models / (MODEL + '.part.abc')).write_bytes(b'partial')
        (self.models / '.download.lock').touch()

    def remove(self, *args, success=True, env=None):
        result = subprocess.run(['bash', SCRIPT, *args], env={**self.env, **(env or {})},
                                capture_output=True, timeout=15, start_new_session=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_full_install_uninstall_round_trip_and_repeat(self):
        (self.home / '.bashrc').write_text('export USER_SETTING=keep\n')
        (self.home / '.bashrc').chmod(0o640)
        self.install()
        self.model()
        self.remove()
        self.assertFalse(self.parent.exists())
        self.assertFalse(self.command.exists() or self.command.is_symlink())
        self.assertEqual((self.home / '.bashrc').read_text(), 'export USER_SETTING=keep\n\n')
        self.assertEqual((self.home / '.bashrc').stat().st_mode & 0o777, 0o640)
        self.assertNotIn('Mika CLI', (self.home / '.profile').read_text())
        self.assertTrue(self.command.parent.exists())
        self.remove()
        self.assertFalse(self.parent.exists())

    def test_no_install_creates_no_files(self):
        self.remove()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_keep_model_flag_and_environment(self):
        for options, env in [(('--keep-model',), {}), ((), {'MIKA_KEEP_MODEL': '1'})]:
            self.install()
            self.model()
            self.remove(*options, env=env)
            self.assertFalse(self.app.exists())
            self.assertEqual((self.models / MODEL).read_bytes(), b'fake model')
        self.remove()
        self.assertFalse(self.parent.exists())

    def test_unrelated_cache_files_and_commands_survive(self):
        self.install()
        self.model()
        self.command.unlink()
        self.command.write_text('unrelated command')
        (self.models / 'notes.txt').write_text('private notes')
        (self.parent / 'other.txt').write_text('unrelated')
        result = self.remove()
        self.assertEqual(self.command.read_text(), 'unrelated command')
        self.assertEqual((self.models / 'notes.txt').read_text(), 'private notes')
        self.assertEqual((self.parent / 'other.txt').read_text(), 'unrelated')
        self.assertFalse((self.models / MODEL).exists())
        self.assertIn(b'unrelated', result.stderr)

    def test_modified_profile_block_and_fish_config_are_preserved(self):
        self.install()
        file = self.home / '.bashrc'
        file.write_text(file.read_text().replace('case ":$PATH:"', 'case ":$CUSTOM_PATH:"'))
        before = file.read_bytes()
        fish = self.home / '.config/fish/conf.d/mika.fish'
        fish.parent.mkdir(parents=True)
        fish.write_text('fish_add_path --path "$HOME/.local/bin"\n# my customization\n')
        self.remove()
        self.assertEqual(file.read_bytes(), before)
        self.assertTrue(fish.exists())

    def test_fish_and_custom_zsh_setup(self):
        self.env['SHELL'] = '/bin/fish'
        self.install()
        fish = self.home / '.config/fish/conf.d/mika.fish'
        self.env['SHELL'] = '/bin/zsh'
        zsh = self.home / 'custom zsh'
        zsh.mkdir()
        self.env['ZDOTDIR'] = str(zsh)
        self.install()
        self.env['SHELL'] = '/bin/bash'  # Cleanup must not depend on the current shell.
        self.remove()
        self.assertFalse(fish.exists())
        self.assertNotIn('Mika CLI', (zsh / '.zshrc').read_text())

    def test_linked_profile_is_not_replaced_or_followed(self):
        self.install()
        file = self.home / '.bashrc'
        target = self.scratch / 'dotfiles'
        file.rename(target)
        file.symlink_to(target)
        before = target.read_bytes()
        self.remove()
        self.assertTrue(file.is_symlink())
        self.assertEqual(target.read_bytes(), before)

    def test_nested_app_and_model_symlinks_do_not_delete_targets(self):
        self.install()
        self.model()
        outside = self.scratch / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('safe')
        (self.app / 'linked-dir').symlink_to(outside, target_is_directory=True)
        (self.models / MODEL).unlink()
        (self.models / MODEL).symlink_to(outside / 'keep')
        self.remove()
        self.assertEqual((outside / 'keep').read_text(), 'safe')

    def test_linked_app_cache_or_parent_is_rejected(self):
        for name in ('app', 'models', 'parent'):
            with self.subTest(name=name):
                self.install()
                self.model()
                path = {'app': self.app, 'models': self.models, 'parent': self.parent}[name]
                target = self.scratch / ('outside-' + name)
                path.rename(target)
                path.symlink_to(target, target_is_directory=True)
                self.remove(success=False)
                self.assertTrue(target.exists())
                path.unlink()
                target.rename(path)
                self.remove()

    def test_missing_or_invalid_ownership_markers_refuse_removal(self):
        self.install()
        marker = self.app / 'ARCHIVE_SHA256'
        original = marker.read_bytes()
        for replacement in (None, b'not a hash\n'):
            if replacement is None:
                marker.unlink()
            else:
                marker.write_bytes(replacement)
            self.remove(success=False)
            self.assertTrue((self.app / 'bin/mika').exists())
            marker.write_bytes(original)

    def test_model_named_directory_refuses_before_removing_app(self):
        self.install()
        self.models.mkdir()
        (self.models / MODEL).mkdir()
        self.remove(success=False)
        self.assertTrue(self.app.exists())

    def test_installer_and_download_locks_prevent_removal(self):
        self.install()
        self.model()
        for path in (self.parent / '.installer.lock', self.models / '.download.lock'):
            with path.open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.remove(success=False)
                self.assertTrue(self.app.exists())
                self.assertTrue((self.models / MODEL).exists())

    def test_symlinked_lock_is_rejected_without_modifying_target(self):
        self.install()
        lock = self.parent / '.installer.lock'
        lock.unlink()
        target = self.scratch / 'lock target'
        target.write_text('do not truncate')
        lock.symlink_to(target)
        self.remove(success=False)
        self.assertEqual(target.read_text(), 'do not truncate')
        self.assertTrue(self.app.exists())

    def test_running_binary_is_not_removed_or_killed(self):
        self.install()
        shutil.copyfile(shutil.which('sleep'), self.app / 'bin/mika')
        process = subprocess.Popen([self.app / 'bin/mika', '60'])
        try:
            self.remove(success=False)
            self.assertIsNone(process.poll())
            self.assertTrue(self.app.exists())
        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_piped_yes_is_not_consent_without_a_controlling_terminal(self):
        self.install()
        self.env['MIKA_UNINSTALL_YES'] = '0'
        result = subprocess.run(['bash'], input=SCRIPT.read_bytes() + b'\ny\n', env=self.env,
                                capture_output=True, start_new_session=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'No interactive terminal', result.stderr)
        self.assertTrue(self.app.exists())

    def terminal_remove(self, answer):
        self.env['MIKA_UNINSTALL_YES'] = '0'
        master, slave = pty.openpty()
        def session():
            os.setsid()
            fcntl.ioctl(slave, __import__('termios').TIOCSCTTY, 0)
        process = subprocess.Popen(['bash'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=slave, env=self.env, preexec_fn=session)
        messages = bytearray()
        try:
            process.stdin.write(SCRIPT.read_bytes())
            process.stdin.close()
            process.stdin = None
            deadline = time.monotonic() + 10
            while b'Remove Mika? [y/N]' not in messages:
                if time.monotonic() > deadline:
                    self.fail(f'No terminal confirmation: {messages!r}')
                if select.select([master], [], [], .1)[0]:
                    messages.extend(os.read(master, 4096))
            os.write(master, answer)
            stdout, _ = process.communicate(timeout=15)
            return process.returncode, stdout
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdin:
                process.stdin.close()
            process.stdout.close()
            os.close(master)
            os.close(slave)

    def test_declined_piped_script_makes_no_changes(self):
        self.install()
        self.model()
        before = {str(path.relative_to(self.home)): path.read_bytes() for path in self.home.rglob('*')
                  if path.is_file() and not path.is_symlink()}
        status, output = self.terminal_remove(b'n\n')
        self.assertEqual(status, 130, output)
        after = {str(path.relative_to(self.home)): path.read_bytes() for path in self.home.rglob('*')
                 if path.is_file() and not path.is_symlink()}
        self.assertEqual(before, after)
        self.assertTrue(self.command.is_symlink())

    def test_accepted_piped_script_removes_only_after_terminal_consent(self):
        self.install()
        self.model()
        status, output = self.terminal_remove(b'y\n')
        self.assertEqual(status, 0, output)
        self.assertFalse(self.parent.exists())

    def test_payload_failure_retains_ownership_for_a_safe_retry(self):
        self.install()
        blocked = self.app / 'blocked-payload'
        blocked.write_text('owned payload')
        tools = self.scratch / 'tools'
        tools.mkdir()
        stub = tools / 'rm'
        real_rm = shutil.which('rm')
        stub.write_text(f'#!{sys.executable}\nimport subprocess, sys\n'
                        f'if sys.argv[-1] == {str(blocked)!r}: sys.exit(23)\n'
                        f'sys.exit(subprocess.call([{real_rm!r}, *sys.argv[1:]]))\n')
        stub.chmod(0o755)
        self.remove(success=False, env={'PATH': str(tools) + os.pathsep + os.environ['PATH']})
        self.assertTrue((self.app / 'VERSION').exists())
        self.assertTrue((self.app / 'ARCHIVE_SHA256').exists())
        self.remove()
        self.assertFalse(self.parent.exists())

    def test_relative_xdg_falls_back_and_flags_are_validated(self):
        self.env['XDG_DATA_HOME'] = 'relative'
        self.install()
        fallback = self.home / '.local/share/mika'
        self.assertTrue(fallback.exists())
        self.remove()
        self.assertFalse(fallback.exists())
        for key in ('MIKA_KEEP_MODEL', 'MIKA_UNINSTALL_YES'):
            self.remove(success=False, env={key: 'invalid'})
        self.remove('--unknown', success=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)

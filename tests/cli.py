"""Offline CLI/PTY tests. All recording tests use fake devices, never a real mic."""
import os
from pathlib import Path
import signal
import re
import subprocess
import sys
import tempfile
import unittest

MIKA = str(Path(sys.argv[1]).resolve())
FIXTURE = str(Path(sys.argv[2]).resolve())
sys.argv = sys.argv[:1]
VERSION = re.search(r'project\(mika VERSION ([^ ]+)', (Path(__file__).resolve().parents[1] / 'CMakeLists.txt').read_text()).group(1)

if os.name == "posix":
    import termios
    from terminal import TerminalProcess


class Arguments(unittest.TestCase):
    def run_cli(self, *args, **options):
        isolation = {"start_new_session": True} if os.name == "posix" else {
            # CREATE_NO_WINDOW can still supply a hidden console/CONIN$ handle.
            # DETACHED_PROCESS is the actual no-controlling-console condition.
            "creationflags": subprocess.DETACHED_PROCESS
        }
        return subprocess.run([MIKA, *args], capture_output=True, timeout=10, **isolation, **options)

    def test_help(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"Enter", result.stdout)
        self.assertIn(b"5 minutes", result.stdout)
        self.assertIn(b"279 MB", result.stdout)
        self.assertIn(b"--raw", result.stdout)
        self.assertIn(b"3 no speech", result.stdout)
        self.assertNotIn(b"--punctuate", result.stdout)
        self.assertEqual(result.stderr, b"")

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, ('mika ' + VERSION + ('\r\n' if os.name == 'nt' else '\n')).encode())
        self.assertEqual(result.stderr, b"")

    @unittest.skipUnless(Path("/dev/full").exists(), "requires the /dev/full failure device")
    def test_informational_stdout_write_failure_is_reported(self):
        for option in ("--help", "--version"):
            with open("/dev/full", "wb") as output:
                result = subprocess.run([MIKA, option], stdout=output, stderr=subprocess.PIPE,
                                        timeout=10, start_new_session=True)
                self.assertEqual(result.returncode, 1)

    def test_unknown_argument_and_removed_setup(self):
        for args in [("--unknown",), ("setup",), ("--help", "extra"), ("--punctuate",), ("--raw", "extra")]:
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"--help", result.stderr)

    def test_no_controlling_terminal_never_reads_piped_consent(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(input=b"y\n", env={**os.environ, "XDG_DATA_HOME": directory, "HOME": directory})
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"no controlling terminal", result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipUnless(sys.platform.startswith("linux"), "XDG paths are Linux-specific")
    def test_xdg_paths_and_relative_fallback(self):
        for xdg, expected in [
            ("/tmp/mika test", "/tmp/mika test/mika/models"),
            ("relative", "/tmp/test home/.local/share/mika/models"),
            ("", "/tmp/test home/.local/share/mika/models"),
            ("/tmp/ends-with-backslash\\", "/tmp/ends-with-backslash\\/mika/models"),
        ]:
            result = self.run_cli("--help", env={**os.environ, "HOME": "/tmp/test home", "XDG_DATA_HOME": xdg})
            self.assertIn(expected.encode(), result.stdout)


@unittest.skipUnless(os.name == "posix", "POSIX PTY controls; Windows needs a native console test")
class Controls(unittest.TestCase):
    def start(self, **env):
        process = TerminalProcess(binary=FIXTURE, env=env)
        self.addCleanup(process.close)
        process.wait_for(b"Listening 00:")
        modes = termios.tcgetattr(process.master)
        self.assertFalse(modes[3] & termios.ECHO)
        self.assertFalse(modes[3] & termios.ICANON)
        return process

    def test_restore_while_parent_shell_keeps_session_alive(self):
        import shlex
        # A shell survives the CLI, so BSD cannot revoke its controlling PTY
        # before the parent observes restoration (success and cancellation).
        command = ('trap "" INT TERM; ' + shlex.quote(FIXTURE) + ' --raw; result=$?; '
                   'printf "CHILD_STATUS:%s\\n" "$result" >&2; read -r ack; exit "$result"')
        for key, expected in ((b'\r', (0, b'Test transcript.\n')), (b'\x1b', (130, b'')), (b'\x03', (130, b''))):
            process = TerminalProcess(binary='/bin/bash', args=('-c', command))
            self.addCleanup(process.close)
            process.wait_for(b'Listening 00:')
            process.send(key)
            process.wait_for(f'CHILD_STATUS:{expected[0]}'.encode())
            self.assertEqual(termios.tcgetattr(process.master), process.before)
            process.send(b'ack\n')
            self.assertEqual(process.finish(), expected)

    def test_enter_prints_only_transcript(self):
        process = self.start()
        self.assertIn(b"/ 05:00", process.messages)
        process.send(b"\r")
        self.assertEqual(process.finish(), (0, b"Test transcript.\n"))

    def test_success_leaves_no_status_lines(self):
        process = self.start()
        process.send(b"\r")
        self.assertEqual(process.finish(), (0, b"Test transcript.\n"))
        # Apply plain carriage-return overwrites as a terminal would.
        line, cursor = [], 0
        for byte in process.messages:
            if byte == 13:
                cursor = 0
            else:
                self.assertGreaterEqual(byte, 32, process.messages)
                if cursor == len(line): line.append(byte)
                else: line[cursor] = byte
                cursor += 1
        self.assertFalse(bytes(line).strip(), process.messages)
        for old_log in (b"Checking model", b"Loading model", b"Opening microphone", b"(CPU)", b"\x1b"):
            self.assertNotIn(old_log, process.messages)

    def test_narrow_dumb_terminal_does_not_wrap_or_use_ansi(self):
        process = TerminalProcess(binary=FIXTURE, columns=32, env={"TERM": "dumb"})
        self.addCleanup(process.close)
        process.wait_for(b"Listening 00:")
        process.send(b"\r")
        self.assertEqual(process.finish(), (0, b"Test transcript.\n"))
        self.assertNotIn(b"\x1b", process.messages)
        self.assertNotIn(b"\n", process.messages)
        self.assertTrue(all(len(part) < 32 for part in process.messages.split(b"\r")))

    def test_redirected_stderr_contains_no_transient_status(self):
        process = TerminalProcess(binary=FIXTURE, redirect_stderr=True, env={"MIKA_FIXTURE_LIMIT": "1"})
        self.addCleanup(process.close)
        self.assertEqual(process.finish(), (0, b"Test transcript.\n"))
        self.assertEqual(process.diagnostics, b"")

    def test_escape_discards_recording(self):
        process = self.start()
        process.send(b"\x1b")
        self.assertEqual(process.finish(), (130, b""))

    def test_control_c_restores_terminal(self):
        process = self.start()
        process.send(b"\x03")
        self.assertEqual(process.finish(), (130, b""))

    def test_sigterm_restores_terminal(self):
        process = self.start()
        process.process.send_signal(signal.SIGTERM)
        self.assertEqual(process.finish(), (130, b""))

    def test_cancel_during_inference(self):
        for key in (b"\x1b", b"\x03"):
            process = self.start(MIKA_FIXTURE_SLOW_INFERENCE="1")
            process.send(b"\r")
            process.wait_for(b"Transcribing")
            process.send(key)
            self.assertEqual(process.finish(), (130, b""))

    def test_lost_terminal_during_inference_is_failure_not_cancellation(self):
        import shlex
        # Ignore SIGHUP as nohup does, so the terminal API observes the loss.
        for args in (('--raw',), ()):
            command = 'trap "" HUP; exec ' + shlex.join([FIXTURE, *args])
            process = TerminalProcess(binary='/bin/bash', args=('-c', command),
                                      env={'MIKA_FIXTURE_SLOW_INFERENCE': '1'})
            self.addCleanup(process.close)
            process.wait_for(b'Listening 00:')
            process.send(b'\r')
            process.wait_for(b'Transcribing')
            process.hangup()
            self.assertEqual(process.finish(), (1, b''))

    def test_broken_stderr_does_not_interrupt_terminal_cleanup(self):
        import shlex
        for flags, expected in (({'MIKA_FIXTURE_DEVICE_LOST': '1'}, 1),
                                ({'MIKA_FIXTURE_GATE_REJECT': '1', 'MIKA_FIXTURE_LIMIT': '1'}, 3)):
            reader, writer = os.pipe()
            os.close(reader)  # The child's stderr is broken before it starts.
            command = (shlex.quote(FIXTURE) + f' --raw 2>&{writer}; result=$?; '
                       'printf "CHILD_STATUS:%s\\n" "$result" >&2; read -r ack; exit "$result"')
            try:
                process = TerminalProcess(binary='/bin/bash', args=('-c', command),
                                          env=flags, pass_fds=(writer,))
            finally:
                os.close(writer)
            self.addCleanup(process.close)
            process.wait_for(f'CHILD_STATUS:{expected}'.encode())
            self.assertEqual(termios.tcgetattr(process.master), process.before)
            process.send(b'ack\n')
            self.assertEqual(process.finish(), (expected, b''))

    def test_inference_error_restores_terminal(self):
        process = self.start(MIKA_FIXTURE_INFERENCE_ERROR="1")
        process.send(b"\r")
        self.assertEqual(process.finish(), (1, b""))

    def test_speech_gate_rejection_is_no_speech(self):
        process = self.start(MIKA_FIXTURE_GATE_REJECT='1')
        process.send(b'\r')
        self.assertEqual(process.finish(), (3, b''))
        self.assertIn(b'No speech recognized', process.messages)

    def test_silence_does_not_create_fake_text(self):
        process = self.start(MIKA_FIXTURE_SILENCE="1")
        process.send(b"\r")
        self.assertEqual(process.finish(), (3, b""))
        self.assertIn(b"No speech recognized", process.messages)

    def test_whitespace_only_is_no_speech(self):
        process = self.start(MIKA_FIXTURE_TEXT=" \t\n")
        process.send(b"\r")
        self.assertEqual(process.finish(), (3, b""))
        self.assertIn(b"No speech recognized", process.messages)

    def test_agent_command_only_runs_after_a_transcript(self):
        import shlex
        command = f'prompt=$({shlex.quote(FIXTURE)} --raw) && printf "AGENT:%s\\n" "$prompt"'
        for flags, expected in [({}, (0, b'AGENT:Test transcript.\n')),
                                ({'MIKA_FIXTURE_SILENCE': '1'}, (3, b'')),
                                ({'MIKA_FIXTURE_INFERENCE_ERROR': '1'}, (1, b''))]:
            process = TerminalProcess(binary='/bin/bash', args=('-c', command),
                                      env={'MIKA_FIXTURE_LIMIT': '1', **flags})
            self.addCleanup(process.close)
            self.assertEqual(process.finish(), expected)

    def test_duration_limit_is_explicit(self):
        process = TerminalProcess(binary=FIXTURE, env={"MIKA_FIXTURE_LIMIT": "1"})
        self.addCleanup(process.close)
        result = process.finish()
        self.assertEqual(result, (0, b"Test transcript.\n"))
        self.assertIn(b"Listening 05:00 / 05:00", process.messages)
        self.assertIn(b"5-minute limit reached", process.messages)

    def test_audio_and_model_failures_do_not_print_text(self):
        for flag in ("MIKA_FIXTURE_AUDIO_ERROR", "MIKA_FIXTURE_DEVICE_LOST", "MIKA_FIXTURE_MODEL_ERROR"):
            process = TerminalProcess(binary=FIXTURE, env={flag: "1"})
            self.addCleanup(process.close)
            self.assertEqual(process.finish(), (1, b""))

    def test_actual_first_run_can_be_declined_without_download(self):
        for key in (b"n", b"\r", b"\x1b", b"\x03"):
            with tempfile.TemporaryDirectory() as directory:
                process = TerminalProcess(binary=MIKA, env={"XDG_DATA_HOME": directory, "HOME": directory})
                self.addCleanup(process.close)
                process.wait_for(b"Download now?")
                process.send(key)
                self.assertEqual(process.finish(), (130, b""))
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_broken_stdout_pipe_does_not_leave_terminal_raw(self):
        process = self.start()
        process.process.stdout.close()
        process.send(b"\r")
        status, _ = process.finish()
        self.assertEqual(status, 1)
        self.assertIn(b'cannot write the transcript', process.messages)


if __name__ == "__main__":
    if sys.platform == 'darwin':
        import faulthandler
        faulthandler.dump_traceback_later(60, repeat=True)
    unittest.main(verbosity=2, failfast=True)

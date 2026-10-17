"""Offline CLI/PTY tests. All recording tests use fake devices, never a real mic."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

MIKA = str(Path(sys.argv[1]).resolve())
FIXTURE = str(Path(sys.argv[2]).resolve())
sys.argv = sys.argv[:1]

if os.name == "posix":
    import fcntl
    import pty
    import select
    import termios

    class TerminalProcess:
        def __init__(self, binary=FIXTURE, env=None):
            self.master, self.slave = pty.openpty()
            self.before = termios.tcgetattr(self.slave)
            self.messages = b""

            def session():
                os.setsid()
                fcntl.ioctl(self.slave, termios.TIOCSCTTY, 0)

            self.process = subprocess.Popen(
                [binary], stdin=self.slave, stdout=subprocess.PIPE, stderr=self.slave,
                env={**os.environ, **(env or {})}, preexec_fn=session,
            )

        def wait_for(self, marker, timeout=10):
            deadline = time.monotonic() + timeout
            while marker not in self.messages:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(f"timeout waiting for {marker!r}: {self.messages!r}")
                ready, _, _ = select.select([self.master], [], [], min(remaining, 0.1))
                if ready:
                    self.messages += os.read(self.master, 4096)
                elif self.process.poll() is not None:
                    raise AssertionError(f"process exited before {marker!r}: {self.messages!r}")

        def send(self, keys):
            os.write(self.master, keys)

        def finish(self):
            try:
                output, _ = self.process.communicate(timeout=10)
                while select.select([self.master], [], [], 0)[0]:
                    self.messages += os.read(self.master, 4096)
                after = termios.tcgetattr(self.slave)
                if after != self.before:
                    raise AssertionError("terminal modes were not restored")
                return self.process.returncode, output
            finally:
                self.close()

        def close(self):
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            if self.process.stdout:
                self.process.stdout.close()
            for name in ("master", "slave"):
                fd = getattr(self, name, None)
                if fd is not None:
                    os.close(fd)
                    setattr(self, name, None)


class Arguments(unittest.TestCase):
    def run_cli(self, *args, **options):
        isolation = {"start_new_session": True} if os.name == "posix" else {
            "creationflags": subprocess.CREATE_NO_WINDOW
        }
        return subprocess.run([MIKA, *args], capture_output=True, timeout=10, **isolation, **options)

    def test_help(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"Enter", result.stdout)
        self.assertIn(b"60 seconds", result.stdout)
        self.assertIn(b"279 MB", result.stdout)
        self.assertEqual(result.stderr, b"")

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"mika 0.1.0\n" if os.name != "nt" else b"mika 0.1.0\r\n")
        self.assertEqual(result.stderr, b"")

    @unittest.skipUnless(Path("/dev/full").exists(), "requires the /dev/full failure device")
    def test_informational_stdout_write_failure_is_reported(self):
        for option in ("--help", "--version"):
            with open("/dev/full", "wb") as output:
                result = subprocess.run([MIKA, option], stdout=output, stderr=subprocess.PIPE,
                                        timeout=10, start_new_session=True)
                self.assertEqual(result.returncode, 1)

    def test_unknown_argument_and_removed_setup(self):
        for args in [("--unknown",), ("setup",), ("--help", "extra")]:
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
        process = TerminalProcess(env=env)
        self.addCleanup(process.close)
        process.wait_for(b"Listening -")
        modes = termios.tcgetattr(process.slave)
        self.assertFalse(modes[3] & termios.ECHO)
        self.assertFalse(modes[3] & termios.ICANON)
        return process

    def test_enter_prints_only_transcript(self):
        process = self.start()
        process.send(b"\r")
        self.assertEqual(process.finish(), (0, b"Test transcript.\n"))

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

    def test_inference_error_restores_terminal(self):
        process = self.start(MIKA_FIXTURE_INFERENCE_ERROR="1")
        process.send(b"\r")
        self.assertEqual(process.finish(), (1, b""))

    def test_silence_does_not_create_fake_text(self):
        process = self.start(MIKA_FIXTURE_SILENCE="1")
        process.send(b"\r")
        self.assertEqual(process.finish(), (0, b"\n"))
        self.assertIn(b"No speech recognized", process.messages)

    def test_duration_limit_is_explicit(self):
        process = TerminalProcess(env={"MIKA_FIXTURE_LIMIT": "1"})
        self.addCleanup(process.close)
        result = process.finish()
        self.assertEqual(result, (0, b"Test transcript.\n"))
        self.assertIn(b"limit reached", process.messages)

    def test_audio_and_model_failures_do_not_print_text(self):
        for flag in ("MIKA_FIXTURE_AUDIO_ERROR", "MIKA_FIXTURE_DEVICE_LOST", "MIKA_FIXTURE_MODEL_ERROR"):
            process = TerminalProcess(env={flag: "1"})
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
        status = process.process.wait(timeout=10)
        self.assertIn(status, (-signal.SIGPIPE, 1))
        self.assertEqual(termios.tcgetattr(process.slave), process.before)


if __name__ == "__main__":
    unittest.main(verbosity=2)

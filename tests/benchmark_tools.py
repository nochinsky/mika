"""Offline benchmark-tool tests; no model, microphone, or global cache changes."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import benchmark_common
import benchmark_durations


class BenchmarkTools(unittest.TestCase):
    def test_exact_duration_and_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source.wav', root / 'output.wav'
            with wave.open(str(source), 'wb') as output:
                output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                output.writeframes(b'\x01\x00' * 3200)
            benchmark_durations.repeated_sample(source, destination, 3)
            with wave.open(str(destination), 'rb') as result:
                self.assertEqual(result.getnframes(), 48000)
                self.assertEqual(result.readframes(48000), b'\x01\x00' * 48000)
            with wave.open(str(source), 'wb') as output:
                output.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
                output.writeframes(b'\x00' * 100)
            with self.assertRaises(ValueError):
                benchmark_durations.repeated_sample(source, destination, 3)

    @unittest.skipUnless(hasattr(os, 'posix_fadvise'), 'POSIX file advice')
    def test_eviction_is_file_local_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'asset'
            path.write_bytes(b'public')
            with patch.object(os, 'posix_fadvise') as advise:
                benchmark_common.evict_files([path, path])
                advise.assert_called_once()
                self.assertEqual(advise.call_args.args[1:], (0, 0, os.POSIX_FADV_DONTNEED))
            self.assertEqual(path.read_bytes(), b'public')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux microphone benchmark')
    def test_microphone_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'report.json'
            result = subprocess.run([sys.executable, ROOT / 'scripts/benchmark_microphone.py',
                                     '--binary', '/does/not/exist', '--output', output],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'requires --allow-microphone', result.stderr)
            self.assertFalse(output.exists())

    def test_recorder_requires_explicit_save_consent(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'private'
            result = subprocess.run([sys.executable, ROOT / 'scripts/record_spoken.py', '--output-dir', output],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'--consent-save-audio is required', result.stderr)
            self.assertFalse(output.exists())

    def test_guided_session_requires_explicit_save_consent(self):
        result = subprocess.run([sys.executable, ROOT / 'scripts/guided_validation.py'],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'--consent-save-audio', result.stderr)
        self.assertIn(b'microphone has not been opened', result.stderr)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux PTY recording fixture')
    def test_guided_recording_with_fake_capture_is_private(self):
        import pty
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tool = root / 'ffmpeg'
            tool.write_text(f'#!{sys.executable}\nimport sys, wave\n'
                            'with wave.open(sys.argv[-1], "wb") as out:\n'
                            '    out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))\n'
                            '    out.writeframes(bytes(3200))\n'
                            'print("out_time_us=100000", flush=True)\nsys.stdin.readline()\n')
            tool.chmod(0o700)
            corpus = root / 'private'
            master, slave = pty.openpty()
            process = subprocess.Popen([sys.executable, ROOT / 'scripts/record_spoken.py',
                                        '--consent-save-audio', '--review', '--output-dir', corpus, '--cases', 'negation'],
                                       stdin=slave, stdout=slave, stderr=slave,
                                       env={**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH']})
            messages = bytearray()
            try:
                def wait_for(marker):
                    deadline = time.monotonic() + 10
                    while marker not in messages:
                        if time.monotonic() > deadline:
                            self.fail(f'Timeout: {messages!r}')
                        if select.select([master], [], [], .1)[0]:
                            messages.extend(os.read(master, 4096))
                wait_for(b'Press Enter when ready')
                os.write(master, b'\n')
                wait_for(b'Recording (maximum')
                os.write(master, b'\n')
                wait_for(b'[Enter] keep this take')
                os.write(master, b'r\n')
                messages.clear()
                wait_for(b'Press Enter when ready')
                os.write(master, b'\n')
                wait_for(b'Recording (maximum')
                os.write(master, b'\n')
                wait_for(b'[Enter] keep this take')
                os.write(master, b'\n')
                self.assertEqual(process.wait(timeout=10), 0, messages)
                audio = corpus / 'audio/negation.wav'
                self.assertTrue(audio.exists())
                self.assertEqual(audio.stat().st_mode & 0o077, 0)
                self.assertEqual((corpus / 'manifest.json').stat().st_mode & 0o077, 0)
                self.assertEqual(len(json.loads((corpus / 'manifest.json').read_text())['cases']), 1)
                self.assertEqual(list(audio.parent.glob('tmp*')), [])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                os.close(slave)

    @unittest.skipUnless(os.name == 'posix', 'executable Python fixture')
    def test_pipeline_runs_and_report_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            probe = root / 'probe'
            probe.write_text(f'#!{sys.executable}\nimport sys\nprint("Hello world.")\n'
                             'print("formatting=0 pipeline_ms=5 peak_rss_kib=12 model_ready_ms=2 '
                             'verify_ms=1 inference=0.003 audio=10.00", file=sys.stderr)\n')
            probe.chmod(0o700)
            sample = root / 'sample.wav'
            sample.write_bytes(b'fake sample')
            output = root / 'report.json'
            result = subprocess.run([sys.executable, ROOT / 'scripts/benchmark_pipeline.py',
                                     '--probe', probe, '--sample', sample, '--model', root / 'unused.gguf',
                                     '--runs', '2', '--output', output], capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(len(report['measurements']['raw']['runs']), 2)
            self.assertEqual(report['measurements']['formatted']['median_speech_inference_ms'], 3)
            self.assertNotIn('Hello world', output.read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Offline native formatting, asset-integrity, raw fallback, and CLI controls.

Uses public/synthetic text and fake audio. Never opens a microphone or downloads.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

PROBE, ASSETS, FAKE, FIXTURE = [Path(arg).resolve() for arg in sys.argv[1:]]
sys.argv = [__file__, str(PROBE), str(FIXTURE)]
import cli  # Reuse PTY harness; its TestCases are not collected in this module.
sys.argv = [__file__]

SHORT = 'hello how are you i am fine thank you i am going home are you coming with me'
# Deterministic native-model smoke output, not a quality-approved reference.
EXPECTED = 'Hello, how are you? I am fine, Thank you, I am going home. are you coming with me?'
RUNTIME = (['onnxruntime.dll', 'mika-fullstop.dll'] if os.name == 'nt' else
           ['libonnxruntime.dylib', 'libmika-fullstop.dylib'] if sys.platform == 'darwin' else
           ['libonnxruntime.so', 'libmika-fullstop.so'])


def words(text):
    return re.sub(r'[,?.]', '', text).lower().split()


class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='Mika punctuation ü ')
        cls.root = Path(cls.temporary.name)
        cls.fake_assets = cls.root / 'fake'
        cls.fake_assets.mkdir()
        for name in ('model.int8.onnx', 'sp.model'):
            shutil.copy2(ASSETS / name, cls.fake_assets / name)
        for name in RUNTIME:
            shutil.copy2(FAKE, cls.fake_assets / name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_probe(self, text=SHORT, assets=ASSETS, env=None, cancel=None):
        with tempfile.TemporaryDirectory(prefix='Mika test ü ') as directory:
            source = Path(directory) / 'input ü.txt'
            source.write_text(text, encoding='utf-8')
            command = [str(PROBE), str(assets), str(source)]
            if cancel is not None:
                command.append(str(cancel))
            return subprocess.run(command, capture_output=True, encoding='utf-8', timeout=30,
                                  env={**os.environ, **(env or {})})

    def test_native_short(self):
        result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, EXPECTED + '\n')

    def test_native_long_all_words_in_order(self):
        phrase = 'and so my fellow americans ask not what your country can do for you ask what you can do for your country'
        text = ' '.join([phrase] * 34)
        self.assertEqual(len(text.split()), 748)
        result = self.run_probe(text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(words(result.stdout), words(text))
        self.assertGreater(result.stdout.count('.'), 10)

    def test_unknown_symbols_and_literals_keep_all_original_characters(self):
        samples = [
            "this is a five-minute test with twenty-five examples",
            "the state-of-the-art method needs a follow-up",
            "open src/main.c and find mika_audio_stop",
            "send the file to jane@example.com tomorrow",
            "keep c++ c# + - _ @ / \\ and 3.14 unchanged",
            "hello. are you ready? don't add duplicate punctuation!",
        ]
        for text in samples:
            result = self.run_probe(text)
            self.assertEqual(result.returncode, 0, result.stderr)
            a, b = text.split(), result.stdout.split()
            self.assertEqual(len(a), len(b))
            for original, restored in zip(a, b):
                self.assertEqual(restored[:len(original)].lower(), original.lower())
                self.assertIn(restored[len(original):], ('', ',', '.', '?'))
                if original[-1] in '.,?!:;\"\'':
                    self.assertEqual(len(original), len(restored))
            self.assertNotIn('<unk>', result.stdout)

    def test_agent_prompt_word_constraints_and_literals(self):
        cases = json.loads(Path(__file__).with_name('prompt_cases.json').read_text())
        for raw in cases:
            with self.subTest(raw=raw):
                result = self.run_probe(raw)
                self.assertEqual(result.returncode, 0, result.stderr)
                original, restored = raw.split(), result.stdout.split()
                self.assertEqual(len(original), len(restored))
                for a, b in zip(original, restored):
                    self.assertEqual(b[:len(a)].lower(), a.lower())
                    self.assertIn(b[len(a):], ('', ',', '.', '?'))
                    camel = any(x.islower() and y.isupper() for x, y in zip(a, a[1:]))
                    acronym = sum(ch.isalpha() for ch in a) >= 2 and a.isupper()
                    if any(c in a for c in '/\\\\_@+#=0123456789') or a.startswith('-') or camel or acronym:
                        self.assertEqual(b[:len(a)], a)

    def test_maximum_input_and_many_window_seams(self):
        # Exact byte limit, ending in a complete word, across many window seams.
        text = 'a ' * 16383 + 'aa'
        self.assertEqual(len(text), 32768)
        result = self.run_probe(text)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(words(result.stdout), text.split())
        self.assertGreater(int(re.search(r'cancel_calls=(\d+)', result.stderr)[1]), 100)

    def test_empty_and_whitespace_need_no_assets(self):
        for text in ('', '   \t'):
            result = self.run_probe(text, assets=self.root / 'missing')
            self.assertEqual((result.returncode, result.stdout), (0, text + '\n'))

    def test_unsupported_input_keeps_raw(self):
        for text in ('a' * 97, 'café near paris', 'hello\x1b[31m'):
            result = self.run_probe(text)
            self.assertEqual((result.returncode, result.stdout), (1, text + '\n'))
            self.assertIn('failure=1', result.stderr)

    def test_missing_assets_keep_raw(self):
        result = self.run_probe(assets=self.root / 'absent')
        self.assertEqual((result.returncode, result.stdout), (1, SHORT + '\n'))
        self.assertIn('failure=2', result.stderr)

    def test_unicode_relocated_assets(self):
        target = self.root / 'Real assets ü space'
        shutil.copytree(ASSETS, target, dirs_exist_ok=True)
        result = self.run_probe(assets=target)
        self.assertEqual((result.returncode, result.stdout), (0, EXPECTED + '\n'), result.stderr)

    def test_corrupt_or_truncated_assets_keep_raw(self):
        target = self.root / 'broken'
        for name in ('model.int8.onnx', 'sp.model'):
            for truncate in (False, True):
                shutil.copytree(self.fake_assets, target, dirs_exist_ok=True)
                data = bytearray((target / name).read_bytes())
                if truncate:
                    del data[-1:]
                else:
                    data[len(data)//2] ^= 1
                (target / name).write_bytes(data)
                result = self.run_probe(assets=target)
                self.assertEqual((result.returncode, result.stdout), (1, SHORT + '\n'), result.stderr)

    def test_missing_runtime_keeps_raw(self):
        target = self.root / 'no-runtime'
        shutil.copytree(self.fake_assets, target, dirs_exist_ok=True)
        (target / RUNTIME[0]).unlink()
        result = self.run_probe(assets=target)
        self.assertEqual((result.returncode, result.stdout), (1, SHORT + '\n'))
        self.assertIn('failure=3', result.stderr)

    def test_native_failure_and_cpp_exceptions_keep_raw(self):
        for failure in ('CREATE_NULL', 'CREATE_THROW', 'APPLY_NULL', 'APPLY_THROW', 'HUGE'):
            result = self.run_probe(assets=self.fake_assets, env={'MIKA_PUNCT_TEST_' + failure: '1'})
            self.assertEqual((result.returncode, result.stdout), (1, SHORT + '\n'), result.stderr)

    def test_unsafe_native_output_keeps_raw(self):
        for out in ('Hello world.', 'Invented words.', SHORT + ' extra', 'Hello\x1b[31m', ''):
            result = self.run_probe(assets=self.fake_assets, env={'MIKA_PUNCT_TEST_OUTPUT': out})
            self.assertEqual((result.returncode, result.stdout), (1, SHORT + '\n'), result.stderr)
            self.assertIn('failure=5', result.stderr)

    def test_case_sensitive_literals_are_independently_guarded(self):
        for raw, wrong in [('open src/main.c', 'Open SRC/main.c.'),
                           ('call mika_audio_stop', 'Call Mika_audio_stop.'),
                           ('send to jane@example.com', 'Send to Jane@example.COM.')]:
            result = self.run_probe(raw, assets=self.fake_assets, env={'MIKA_PUNCT_TEST_OUTPUT': wrong})
            self.assertEqual((result.returncode, result.stdout), (1, raw + '\n'))
        for raw in ('open src/main.c', 'call mika_audio_stop', 'send to jane@example.com'):
            result = self.run_probe(raw)
            self.assertEqual(result.returncode, 0, result.stderr)
            for a, b in zip(raw.split(), result.stdout.split()):
                if any(mark in a for mark in ('/', '_', '@')):
                    self.assertEqual(b[:len(a)], a)

    def test_missing_entrypoint_keeps_raw(self):
        target = self.root / 'wrong-module'
        shutil.copytree(self.fake_assets, target, dirs_exist_ok=True)
        shutil.copy2(ASSETS / RUNTIME[0], target / RUNTIME[1])
        result = self.run_probe(assets=target)
        self.assertEqual((result.returncode, result.stdout), (1, SHORT + '\n'))

    def test_native_cancellation_status_discards_allocated_output(self):
        result = self.run_probe(assets=self.fake_assets, env={'MIKA_PUNCT_TEST_CANCEL': '1'})
        self.assertEqual((result.returncode, result.stdout), (130, ''))

    def test_native_case_and_punctuation_only_allowed(self):
        result = self.run_probe(assets=self.fake_assets, env={'MIKA_PUNCT_TEST_OUTPUT': EXPECTED})
        self.assertEqual((result.returncode, result.stdout), (0, EXPECTED + '\n'))

    def test_cancellation_before_load_after_load_and_after_inference(self):
        completed = self.run_probe()
        calls = int(re.search(r'cancel_calls=(\d+)', completed.stderr)[1])
        self.assertGreaterEqual(calls, 9)
        for at in range(1, calls + 1):
            result = self.run_probe(cancel=at)
            self.assertEqual((result.returncode, result.stdout), (130, ''), result.stderr)
        long_text = ' '.join(['and so my fellow americans ask not what your country can do for you'] * 40)
        completed = self.run_probe(long_text)
        long_calls = int(re.search(r'cancel_calls=(\d+)', completed.stderr)[1])
        self.assertGreater(long_calls, calls)
        for at in (long_calls - 3, long_calls - 2, long_calls - 1, long_calls):
            result = self.run_probe(long_text, cancel=at)
            self.assertEqual((result.returncode, result.stdout), (130, ''), result.stderr)


@unittest.skipUnless(os.name == 'posix', 'POSIX PTY; native Windows console checked separately')
class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='Mika relocated ü ')
        cls.root = Path(cls.temporary.name)
        cls.binary = cls.root / FIXTURE.name
        shutil.copy2(FIXTURE, cls.binary)
        shutil.copytree(ASSETS, cls.root / 'punctuation')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def start(self, binary=FIXTURE, raw=False, redirect=False, **env):
        process = cli.TerminalProcess(binary=str(binary), args=['--raw'] if raw else [],
                                      env={'MIKA_FIXTURE_TEXT': SHORT, **env}, redirect_stderr=redirect)
        self.addCleanup(process.close)
        if not redirect:
            process.wait_for(b'Listening 00:')
        return process

    def test_raw_option_does_not_format(self):
        process = self.start(raw=True)
        process.send(b'\r')
        self.assertEqual(process.finish(), (0, (SHORT + '\n').encode()))
        self.assertNotIn(b'Formatting', process.messages)

    def test_real_formatter_clean_redirected_stdout_and_relocation(self):
        process = self.start(binary=self.binary)
        process.send(b'\r')
        self.assertEqual(process.finish(), (0, (EXPECTED + '\n').encode()))
        self.assertNotIn(b'keeping the raw', process.messages)
        # Carriage-return UI is completely erased after success.
        line, cursor = [], 0
        for byte in process.messages:
            if byte == 13:
                cursor = 0
            else:
                self.assertGreaterEqual(byte, 32)
                if cursor == len(line): line.append(byte)
                else: line[cursor] = byte
                cursor += 1
        self.assertFalse(bytes(line).strip(), process.messages)

    def test_redirected_stderr_is_quiet(self):
        process = self.start(redirect=True, MIKA_FIXTURE_LIMIT='1')
        self.assertEqual(process.finish(), (0, (EXPECTED + '\n').encode()))
        self.assertEqual(process.diagnostics, b'')

    def test_escape_or_control_c_prints_no_transcript(self):
        for key in (b'\x1b', b'\x03'):
            process = self.start()
            process.send(key)
            self.assertEqual(process.finish(), (130, b''))

    def test_no_speech_default_never_prints_or_formats(self):
        for value in ('', ' \t\n'):
            process = self.start(redirect=True, MIKA_FIXTURE_LIMIT='1', MIKA_FIXTURE_TEXT=value)
            self.assertEqual(process.finish(), (3, b''))
            self.assertEqual(process.diagnostics, b'No speech recognized.\n')

    def test_raw_without_formatter_files_is_clean(self):
        target = self.root / 'raw-only'
        target.mkdir(exist_ok=True)
        binary = target / FIXTURE.name
        shutil.copy2(FIXTURE, binary)
        process = self.start(binary=binary, raw=True, redirect=True, MIKA_FIXTURE_LIMIT='1')
        self.assertEqual(process.finish(), (0, (SHORT + '\n').encode()))
        self.assertEqual(process.diagnostics, b'')

    def test_backend_failure_keeps_raw(self):
        missing = self.root / 'missing'
        missing.mkdir(exist_ok=True)
        binary = missing / FIXTURE.name
        shutil.copy2(FIXTURE, binary)
        process = self.start(binary=binary)
        process.send(b'\r')
        self.assertEqual(process.finish(), (0, (SHORT + '\n').encode()))
        self.assertIn(b'formatting data is missing', process.messages)
        self.assertIn(b'keeping the raw transcript', process.messages)

    def test_unsupported_text_falls_back_without_losing_unicode(self):
        process = self.start(redirect=True, MIKA_FIXTURE_LIMIT='1', MIKA_FIXTURE_TEXT='café near paris')
        self.assertEqual(process.finish(), (0, 'café near paris\n'.encode()))
        self.assertIn(b'text is outside formatting limits', process.diagnostics)
        self.assertNotIn('café'.encode(), process.diagnostics)

    def test_cancel_during_formatter_discards_everything(self):
        target = self.root / 'slow'
        target.mkdir(exist_ok=True)
        binary = target / FIXTURE.name
        shutil.copy2(FIXTURE, binary)
        assets = target / 'punctuation'
        assets.mkdir(exist_ok=True)
        for name in ('model.int8.onnx', 'sp.model'):
            shutil.copy2(ASSETS / name, assets / name)
        for name in RUNTIME:
            shutil.copy2(FAKE, assets / name)
        for key in (b'\x1b', b'\x03'):
            process = self.start(binary=binary, MIKA_PUNCT_TEST_SLOW='1')
            process.send(b'\r')
            process.wait_for(b'punctuation-test: inference started')
            process.send(key)
            self.assertEqual(process.finish(), (130, b''))


class WindowsConsole(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'native Windows only')
    def test_real_formatter_classic_console(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('windows_console.py')),
                                 str(FIXTURE)], capture_output=True, timeout=60,
                                env={**os.environ, 'MIKA_FIXTURE_TEXT': SHORT, 'MIKA_FIXTURE_EXPECTED_OUTPUT': EXPECTED})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(os.name == 'nt', 'native Windows only')
    def test_no_speech_classic_console(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('windows_console.py')),
                                 str(FIXTURE)], capture_output=True, timeout=60,
                                env={**os.environ, 'MIKA_FIXTURE_SILENCE': '1'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(os.name == 'nt', 'native Windows only')
    def test_cancel_during_native_formatter(self):
        with tempfile.TemporaryDirectory(prefix='Mika fake ü ') as directory:
            root = Path(directory)
            binary = root / FIXTURE.name
            shutil.copy2(FIXTURE, binary)
            assets = root / 'punctuation'
            assets.mkdir()
            for name in ('model.int8.onnx', 'sp.model'):
                shutil.copy2(ASSETS / name, assets / name)
            for name in RUNTIME:
                shutil.copy2(FAKE, assets / name)
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('windows_console.py')),
                                     str(binary)], capture_output=True, timeout=60,
                                    env={**os.environ, 'MIKA_FIXTURE_TEXT': SHORT,
                                         'MIKA_PUNCT_TEST_SLOW': '1', 'MIKA_FIXTURE_CANCEL_DURING_FORMAT': '1'})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)

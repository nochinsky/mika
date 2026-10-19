"""Offline scorer/privacy/fixture tests. No real model or microphone."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import evaluate_spoken as evaluation


class SpokenEvaluation(unittest.TestCase):
    def test_word_errors(self):
        result = evaluation.word_errors('one two three', 'one four three extra')
        self.assertEqual((result['errors'], result['substitutions'], result['deletions'], result['insertions']), (2, 1, 0, 1))
        self.assertEqual(evaluation.word_errors('do not commit', 'do commit')['deletions'], 1)
        self.assertEqual(evaluation.word_errors("Can't do that.", "can't do that")['errors'], 0)
        self.assertEqual(evaluation.word_errors('word', 'one two three')['wer'], 3)
        self.assertEqual(evaluation.word_errors('hello world', '')['deletions'], 2)
        with self.assertRaises(ValueError):
            evaluation.word_errors('', 'invented')

    def test_critical_checks_preserve_literals_and_negation(self):
        checks = [{'label': 'negation', 'expected': 'do not commit'},
                  {'label': 'identifier', 'expected': 'API_KEY', 'case_sensitive': True},
                  {'label': 'number', 'expected': '16 threads', 'acceptable': ['sixteen threads']}]
        self.assertEqual(evaluation.critical_flags(checks, 'Do not commit API_KEY. Use sixteen threads.'), [])
        flags = evaluation.critical_flags(checks, 'Do commit api_key with 60 threads')
        self.assertEqual(len(flags), 3)
        self.assertFalse(evaluation.phrase_present('foo_bar', 'foo bar'))
        self.assertFalse(evaluation.phrase_present('not', 'nothing'))
        self.assertTrue(evaluation.phrase_present('0.1.2', 'version 0.1.2.'))
        forbidden = [{'label': 'wrong number', 'expected': '16', 'forbidden': ['60']}]
        self.assertTrue(evaluation.critical_flags(forbidden, '16 and 60')[0]['forbidden_present'])

    def test_authored_prompts_are_valid_but_not_claimed_as_audio(self):
        manifest = evaluation.load_manifest(ROOT / 'tests/spoken_prompt_cases.json')
        self.assertEqual(len(manifest['cases']), 12)
        self.assertIn('NOT recorded', manifest['scope'])
        for case in manifest['cases']:
            self.assertEqual(evaluation.compare(case, case['reference'])['wer'], 0)
            self.assertEqual(evaluation.critical_flags(case.get('critical_checks', []), case['reference']), [])

    def test_predeclared_alternatives(self):
        case = {'reference': '16 threads', 'acceptable_references': ['sixteen threads']}
        result = evaluation.compare(case, 'Sixteen threads.')
        self.assertEqual((result['wer'], result['reference_index']), (0, 1))

    def test_invalid_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'manifest.json'
            case = {'id': 'a', 'audio': 'a.wav', 'reference': 'hello',
                    'critical_checks': [{'label': 'bad', 'expected': 'missing'}]}
            for cases in ([], [case], [{**case, 'critical_checks': [], 'id': '../bad'}]):
                path.write_text(json.dumps({'schema_version': 1, 'cases': cases}))
                with self.assertRaises(ValueError):
                    evaluation.load_manifest(path)

    @unittest.skipUnless(os.name == 'posix', 'executable Python fixture')
    def test_report_omits_transcripts_unless_explicitly_requested(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            probe = root / 'probe'
            probe.write_text(f'#!{sys.executable}\nimport sys\nprint("Private test phrase.")\n'
                             'print("formatting=0 pipeline_ms=1 peak_rss_kib=2 model_ready_ms=1", file=sys.stderr)\n')
            probe.chmod(0o700)
            (root / 'sample.wav').write_bytes(b'fake audio consumed only by the fake probe')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'schema_version': 1, 'cases': [
                {'id': 'privacy', 'audio': 'sample.wav', 'reference': 'Private test phrase'}]}))
            output = root / 'report.json'
            command = [sys.executable, ROOT / 'scripts/evaluate_spoken.py', '--probe', probe,
                       '--model', root / 'unused.gguf', '--manifest', manifest, '--output', output]
            result = subprocess.run(command, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('Private test phrase', output.read_text())
            self.assertEqual(json.loads(output.read_text())['summary']['raw']['wer'], 0)
            result = subprocess.run([*command, '--include-transcripts'], capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Private test phrase', output.read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)

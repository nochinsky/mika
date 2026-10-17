"""Offline checks of authored fixtures and the quality-report math, not model quality."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evaluation', ROOT / 'scripts/evaluate_punctuation.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class Evaluation(unittest.TestCase):
    def test_fixtures_keep_identical_words(self):
        for name in ('punctuation_cases.json', 'punctuation_holdout.json'):
            cases = json.loads((ROOT / 'tests' / name).read_text(encoding='utf-8'))
            self.assertGreaterEqual(len(cases), 30)
            seen = set()
            for case in cases:
                self.assertNotIn(case['raw'], seen)
                seen.add(case['raw'])
                primary_questions = {e for e in evaluation.events(case['raw'], case['expected'])[0] if e[-1] == '?'}
                for expected in [case['expected'], *case.get('acceptable', [])]:
                    p, _ = evaluation.events(case['raw'], expected)
                    if {e for e in p if e[-1] == '?'} != primary_questions:
                        self.assertTrue(case.get('ambiguous'), 'Question ambiguity must be explicit')

    def test_holdout_is_disjoint_and_has_hard_cases(self):
        first = json.loads((ROOT / 'tests/punctuation_cases.json').read_text())
        second = json.loads((ROOT / 'tests/punctuation_holdout.json').read_text())
        self.assertFalse({c['raw'] for c in first} & {c['raw'] for c in second})
        for category in ('question', 'command', 'name', 'literal', 'ambiguity', 'fragment', 'disfluency'):
            self.assertTrue(any(c['category'] == category for c in second))

    def test_event_and_micro_score_math(self):
        p, c = evaluation.events('hello how are you', 'Hello, how are you?')
        self.assertEqual(p, {(0, ','), (3, '?')})
        self.assertEqual(c, {(0, 0, 'H')})
        result = evaluation.score({1, 2}, {2, 3})
        self.assertEqual((result['tp'], result['fp'], result['fn']), (1, 1, 1))
        self.assertEqual(result['f1'], .5)
        self.assertEqual(evaluation.score(set(), set())['f1'], 0)

    def test_word_mutations_are_not_quality_success(self):
        for output in ('fifteen', 'fifty extra', '', 'fifty!', 'fifty..'):
            with self.assertRaises(AssertionError):
                evaluation.events('fifty', output)
        evaluation.events("can't five-minute 0.1.2", "Can't five-minute 0.1.2.")


if __name__ == '__main__':
    unittest.main(verbosity=2)

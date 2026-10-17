"""Small authored quality tripwire, not a natural-dictation accuracy benchmark.

References reflect one writer's choices; legitimate punctuation alternatives can
score as mismatches. A failed quality gate is a research finding, not permission
to rewrite words or tune this corpus until it passes. Never records or downloads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def events(raw, output):
    original, restored = raw.split(), output.split()
    assert len(original) == len(restored), 'Word count changed'
    punctuation, casing = set(), set()
    for i, (a, b) in enumerate(zip(original, restored)):
        assert b[:len(a)].lower() == a.lower(), 'Word changed'
        suffix = b[len(a):]
        assert suffix in ('', ',', '.', '?'), 'Unexpected punctuation'
        if suffix:
            punctuation.add((i, suffix))
        for j, (old, new) in enumerate(zip(a, b)):
            if old != new:
                casing.add((i, j, new))
    return punctuation, casing


def score(predicted, expected):
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return dict(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, default=Path(__file__).resolve().parents[1] / 'tests/punctuation_cases.json')
    args = parser.parse_args()
    cases = json.loads(args.corpus.read_text(encoding='utf-8'))
    pred_p, gold_p, pred_c, gold_c = set(), set(), set(), set()
    results = []
    for number, case in enumerate(cases):
        raw, expected = case['raw'], case['expected']
        with tempfile.TemporaryDirectory(prefix='Mika authored text ü ') as directory:
            source = Path(directory) / 'input.txt'
            source.write_text(raw, encoding='utf-8')
            result = subprocess.run([str(args.probe.resolve()), str(args.assets.resolve()), str(source)],
                                    capture_output=True, encoding='utf-8', timeout=30)
        assert result.returncode in (0, 1), result.stderr
        output = result.stdout.rstrip('\r\n')
        p, c = events(raw, output)
        gp, gc = events(raw, expected)
        pred_p.update((number, *event) for event in p)
        gold_p.update((number, *event) for event in gp)
        pred_c.update((number, *event) for event in c)
        gold_c.update((number, *event) for event in gc)
        results.append({**case, 'output': output, 'fallback': result.returncode == 1,
                        'exact_reference': output == expected})
    punctuation = score(pred_p, gold_p)
    casing = score(pred_c, gold_c)
    question = score({event for event in pred_p if event[-1] == '?'},
                     {event for event in gold_p if event[-1] == '?'})
    fallbacks = sum(case['fallback'] for case in results)
    # Preliminary bar chosen before running this corpus, not a claim that passing
    # 30 authored examples establishes production quality on real dictation.
    thresholds = {'punctuation_f1': 0.90, 'casing_f1': 0.90, 'question_recall': 0.90}
    gate = not fallbacks and punctuation['f1'] >= .90 and casing['f1'] >= .90 and question['recall'] >= .90
    report = dict(corpus='30 authored text examples; not real microphone dictation',
                  corpus_sha256=hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
                  examples=len(cases), word_preservation='all examples passed', fallbacks=fallbacks,
                  punctuation=punctuation, casing=casing, questions=question,
                  exact_references=sum(case['exact_reference'] for case in results),
                  preliminary_thresholds=thresholds, preliminary_quality_gate_passed=bool(gate),
                  cases=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'cases'}, indent=2))
    print('Report:', args.output)


if __name__ == '__main__':
    main()

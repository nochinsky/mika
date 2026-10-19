"""Opt-in evaluation of explicitly supplied audio/reference manifests.

WER is measured against predeclared references. Critical-phrase mismatches are
REVIEW FLAGS, not an automatic semantic-accuracy judgment. Both raw ASR and the
formatted pipeline are checked. Audio never leaves the machine. Reports omit
transcripts by default; --include-transcripts explicitly retains private text.
No recording, corpus discovery, synthetic speech, or downloads occur here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from benchmark_common import environment
from evaluate_punctuation import events


def words(text):
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)*", text.casefold().replace('’', "'"), re.UNICODE)


def word_errors(reference, hypothesis):
    expected, actual = words(reference), words(hypothesis)
    if not expected:
        raise ValueError('Reference must contain words')
    # (edit cost, substitutions, deletions, insertions), deterministic tie breaks.
    previous = [(i, 0, 0, i) for i in range(len(actual) + 1)]
    for i, a in enumerate(expected, 1):
        current = [(i, 0, i, 0)]
        for j, b in enumerate(actual, 1):
            if a == b:
                current.append(previous[j - 1])
                continue
            diagonal, above, left = previous[j - 1], previous[j], current[j - 1]
            candidates = [(diagonal[0] + 1, diagonal[1] + 1, diagonal[2], diagonal[3]),
                          (above[0] + 1, above[1], above[2] + 1, above[3]),
                          (left[0] + 1, left[1], left[2], left[3] + 1)]
            current.append(min(candidates, key=lambda value: value[0]))
        previous = current
    edits, substitutions, deletions, insertions = previous[-1]
    return {'reference_words': len(expected), 'errors': edits, 'substitutions': substitutions,
            'deletions': deletions, 'insertions': insertions, 'wer': edits / len(expected)}


def phrase_present(phrase, text, case_sensitive=False):
    # Preserve internal identifier/path punctuation: foo_bar is NOT "foo bar".
    def tokens(value):
        if not case_sensitive:
            value = value.casefold()
        return [word.strip('.,?!;:"()') for word in value.split()]
    needle, haystack = tokens(phrase), tokens(text)
    return bool(needle) and any(haystack[i:i + len(needle)] == needle
                               for i in range(len(haystack) - len(needle) + 1))


def critical_flags(checks, hypothesis):
    flags = []
    for check in checks:
        sensitive = check.get('case_sensitive', False)
        expected = [check['expected'], *check.get('acceptable', [])]
        missing = not any(phrase_present(term, hypothesis, sensitive) for term in expected)
        forbidden = [term for term in check.get('forbidden', []) if phrase_present(term, hypothesis, sensitive)]
        if missing or forbidden:
            flags.append({'label': check['label'], 'expected_missing': missing, 'forbidden_present': forbidden})
    return flags


def load_manifest(path):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('cases'), list) or not manifest['cases']:
        raise ValueError('Expected schema_version 1 and nonempty cases')
    seen = set()
    for case in manifest['cases']:
        identifier = case['id']
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', identifier) or identifier in seen:
            raise ValueError('Case IDs must be unique safe identifiers')
        seen.add(identifier)
        references = [case['reference'], *case.get('acceptable_references', [])]
        for reference in references:
            word_errors(reference, reference)
        for check in case.get('critical_checks', []):
            expected = [check['expected'], *check.get('acceptable', [])]
            if not check.get('label') or not all(any(phrase_present(term, ref, check.get('case_sensitive', False))
                                                   for ref in references) for term in expected):
                raise ValueError('Critical expected phrases must occur in a predeclared reference')
        audio = Path(case['audio'])
        if not audio.is_absolute():
            audio = path.parent / audio
        case['_audio'] = audio.resolve()
    return manifest


def compare(case, hypothesis):
    references = [case['reference'], *case.get('acceptable_references', [])]
    scores = [word_errors(reference, hypothesis) for reference in references]
    best = min(range(len(scores)), key=lambda i: scores[i]['wer'])
    return {**scores[best], 'reference_index': best,
            'critical_review_flags': critical_flags(case.get('critical_checks', []), hypothesis)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--include-transcripts', action='store_true')
    args = parser.parse_args()
    manifest = load_manifest(args.manifest.resolve())
    missing = [case['id'] for case in manifest['cases'] if not case['_audio'].is_file()]
    if missing:
        parser.error('Missing explicitly supplied audio for: ' + ', '.join(missing))
    report = {'scope': __doc__, 'environment': environment(), 'transcripts_retained': args.include_transcripts,
              'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(), 'cases': []}
    failed = 0
    for case in manifest['cases']:
        row = {'id': case['id'], 'audio_sha256': hashlib.sha256(case['_audio'].read_bytes()).hexdigest()}
        outputs = {}
        for mode in ('raw', 'formatted'):
            command = [str(args.probe.resolve()), str(args.model.resolve()), str(case['_audio'])]
            if mode == 'raw':
                command.append('--raw')
            process = subprocess.run(command, capture_output=True, encoding='utf-8', timeout=600)
            row[mode] = {'exit_code': process.returncode}
            if process.returncode:
                failed += 1
                continue
            hypothesis = process.stdout.rstrip('\r\n')
            outputs[mode] = hypothesis
            row[mode].update(compare(case, hypothesis))
            fields = dict(re.findall(r'(\w+)=([\d.]+)', process.stderr))
            for name in ('pipeline_ms', 'peak_rss_kib', 'model_ready_ms'):
                if name in fields:
                    row[mode][name] = float(fields[name])
            if mode == 'formatted':
                row[mode]['formatting_fallback'] = fields.get('formatting') != '0'
            if args.include_transcripts:
                row[mode]['hypothesis'] = hypothesis
        if len(outputs) == 2:
            try:
                events(outputs['raw'], outputs['formatted'])
                row['formatting_preserved_words'] = True
            except AssertionError:
                row['formatting_preserved_words'] = False
                failed += 1
        if args.include_transcripts:
            row['reference'] = case['reference']
        report['cases'].append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    report['summary'] = {'cases': len(report['cases']), 'pipeline_or_preservation_failures': failed}
    for mode in ('raw', 'formatted'):
        rows = [case[mode] for case in report['cases'] if 'wer' in case[mode]]
        count = sum(row['reference_words'] for row in rows)
        report['summary'][mode] = {'scored_cases': len(rows), 'wer': sum(row['errors'] for row in rows) / count if count else None,
                                   'cases_flagged_for_critical_review': sum(bool(row['critical_review_flags']) for row in rows)}
    report['summary']['interpretation'] = 'Review flags and WER are evidence, not a semantic guarantee or automatic release approval.'
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

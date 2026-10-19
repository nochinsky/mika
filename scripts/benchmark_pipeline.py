"""Public-file ASR -> optional formatting probe, not microphone/end-user timing.

Five fresh processes per mode by default. Normal filesystem caches unless file-local
best-effort eviction is requested; neither mode guarantees cold caches. Includes WAV decoding,
speech-model load/inference, optional complete formatting stage, and teardown.
Includes the CLI's full Granite checksum verification; excludes microphone capture
and console UI. Model-ready timing covers checksum plus speech-engine loading,
not microphone opening or measured end-to-end time to the Listening status.
Reports whole-process peak RSS/Windows peak working set, not an additive RAM cost.
Never records audio, downloads assets, or stores transcripts in the JSON report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import statistics
import subprocess
from evaluate_punctuation import events
from benchmark_common import cache_files, environment, evict_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--cache-mode', choices=('warm', 'evict'), default='warm',
                        help='evict requests file-local eviction; not guaranteed cold caches')
    args = parser.parse_args()
    if not 1 <= args.runs <= 20:
        parser.error('--runs must be between 1 and 20')
    report = {'platform': platform.platform(), 'environment': environment(), 'scope': __doc__,
              'cache_mode': args.cache_mode,
              'cache_note': ('Normal filesystem caches; no prewarming or eviction.' if args.cache_mode == 'warm'
                             else 'File-local POSIX_FADV_DONTNEED before each run; best effort, not guaranteed cold.'),
              'sample': args.sample.name, 'sample_sha256': hashlib.sha256(args.sample.read_bytes()).hexdigest(),
              'measurements': {}}
    original = None
    for mode in ('raw', 'formatted'):
        runs = []
        for _ in range(args.runs):
            if args.cache_mode == 'evict':
                evict_files(cache_files(args.probe, args.model, args.sample))
            command = [str(args.probe.resolve()), str(args.model.resolve()), str(args.sample.resolve())]
            if mode == 'raw':
                command.append('--raw')
            result = subprocess.run(command, capture_output=True, encoding='utf-8', timeout=600)
            assert result.returncode == 0, result.stderr
            fields = dict(re.findall(r'(\w+)=([\d.]+)', result.stderr))
            text = result.stdout.rstrip('\r\n')
            if original is None:
                original = text
            if mode == 'formatted':
                assert fields['formatting'] == '0', result.stderr
                events(original, text)
            else:
                assert text == original, 'Raw inference changed between identical runs'
            runs.append({'pipeline_ms': float(fields['pipeline_ms']),
                         'peak_rss_kib': int(fields['peak_rss_kib']),
                         'model_ready_ms': float(fields['model_ready_ms']),
                         'verify_ms': float(fields['verify_ms']),
                         'speech_inference_ms': float(fields['inference']) * 1000,
                         'audio_seconds': float(fields['audio'])})
        report['measurements'][mode] = {
            'runs': runs,
            'median_pipeline_ms': statistics.median(row['pipeline_ms'] for row in runs),
            'median_model_ready_ms': statistics.median(row['model_ready_ms'] for row in runs),
            'median_verify_ms': statistics.median(row['verify_ms'] for row in runs),
            'median_speech_inference_ms': statistics.median(row['speech_inference_ms'] for row in runs),
            'audio_seconds': runs[0]['audio_seconds'],
            'median_process_peak_rss_kib': statistics.median(row['peak_rss_kib'] for row in runs),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

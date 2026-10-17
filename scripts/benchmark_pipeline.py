"""Public-file ASR -> optional formatting probe, not microphone/end-user timing.

Five fresh processes per mode, normal filesystem caches. Includes WAV decoding,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'platform': platform.platform(), 'scope': __doc__,
              'sample': args.sample.name, 'sample_sha256': hashlib.sha256(args.sample.read_bytes()).hexdigest(),
              'measurements': {}}
    original = None
    for mode in ('raw', 'formatted'):
        runs = []
        for _ in range(5):
            command = [str(args.probe.resolve()), str(args.model.resolve()), str(args.sample.resolve())]
            if mode == 'raw':
                command.append('--raw')
            result = subprocess.run(command, capture_output=True, encoding='utf-8', timeout=120)
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
                         'model_ready_ms': float(fields['model_ready_ms'])})
        report['measurements'][mode] = {
            'runs': runs,
            'median_pipeline_ms': statistics.median(row['pipeline_ms'] for row in runs),
            'median_model_ready_ms': statistics.median(row['model_ready_ms'] for row in runs),
            'median_process_peak_rss_kib': statistics.median(row['peak_rss_kib'] for row in runs),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

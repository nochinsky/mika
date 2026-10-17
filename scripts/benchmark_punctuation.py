"""Native punctuation-only stage measurements, not incremental/end-to-end Mika RAM.

Five fresh processes per input. Normal filesystem caches, one ONNX inference
thread. The upstream tokenizer additionally creates an idle hardware-sized pool;
this is NOT a single-OS-thread claim. Inputs are synthetic/public, not dictation.
"""
import argparse
import json
from pathlib import Path
import platform
import re
import statistics
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    phrase = 'and so my fellow americans ask not what your country can do for you ask what you can do for your country'
    inputs = {'short': 'hello how are you i am fine thank you i am going home are you coming with me',
              'long': ' '.join([phrase] * 34)}
    report = {'platform': platform.platform(), 'processor': platform.processor(),
              'note': __doc__, 'measurements': {}}
    for name, text in inputs.items():
        rows = []
        with tempfile.TemporaryDirectory(prefix='Mika public benchmark ') as directory:
            source = Path(directory) / 'input.txt'
            source.write_text(text, encoding='utf-8')
            for _ in range(5):
                result = subprocess.run([str(args.probe.resolve()), str(args.assets.resolve()), str(source)],
                                        capture_output=True, encoding='utf-8', timeout=60)
                assert result.returncode == 0, result.stderr
                assert re.sub(r'[,?.]', '', result.stdout).lower().split() == text.lower().split()
                fields = dict(re.findall(r'(\w+)=([\d.]+)', result.stderr))
                rows.append({'stage_ms': float(fields['format_ms']), 'peak_rss_kib': int(fields['peak_rss_kib'])})
        report['measurements'][name] = {'words': len(text.split()), 'characters': len(text), 'runs': rows,
            'median_stage_ms': statistics.median(row['stage_ms'] for row in rows),
            'median_process_peak_rss_kib': statistics.median(row['peak_rss_kib'] for row in rows)}
    payload = args.assets
    report['payload_bytes_including_notices'] = sum(p.stat().st_size for p in payload.rglob('*') if p.is_file())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

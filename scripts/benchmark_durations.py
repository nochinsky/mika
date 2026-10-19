"""Duration/resource regression from repeated public PCM, NOT natural-speech accuracy.

Generates exact-length 10/60/300-second mono PCM WAVs in a temporary directory.
Repeats the supplied public sample without claiming varied or natural dictation.
Runs both raw and formatted file pipelines; never opens a microphone.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
from benchmark_common import environment


def repeated_sample(sample, destination, seconds):
    with wave.open(str(sample), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 16000, 'NONE'):
            raise ValueError('Expected mono 16-bit 16 kHz uncompressed public WAV')
        pcm = source.readframes(source.getnframes())
    if not pcm:
        raise ValueError('Empty sample')
    remaining = seconds * 16000 * 2
    with wave.open(str(destination), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        while remaining:
            block = pcm[:remaining]
            output.writeframesraw(block)
            remaining -= len(block)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--sample', type=Path, required=True, help='Public human-speech sample, not private audio')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--durations', type=int, nargs='+', default=[10, 60, 300])
    parser.add_argument('--cache-modes', choices=('warm', 'evict'), nargs='+', default=['warm'])
    args = parser.parse_args()
    if not 1 <= args.runs <= 20 or any(not 1 <= value <= 300 for value in args.durations):
        parser.error('Use 1–20 runs and durations between 1 and 300 seconds')
    report = {'scope': __doc__, 'environment': environment(),
              'source_sha256': hashlib.sha256(args.sample.read_bytes()).hexdigest(), 'measurements': {}}
    with tempfile.TemporaryDirectory(prefix='mika-public-durations-') as scratch:
        root = Path(scratch)
        for seconds in args.durations:
            sample = root / f'public-{seconds}s.wav'
            repeated_sample(args.sample, sample, seconds)
            for mode in dict.fromkeys(args.cache_modes):
                output = root / 'report.json'
                subprocess.run([sys.executable, str(Path(__file__).with_name('benchmark_pipeline.py')),
                                '--probe', str(args.probe.resolve()), '--model', str(args.model.resolve()),
                                '--sample', str(sample), '--output', str(output), '--runs', str(args.runs),
                                '--cache-mode', mode], check=True, stdout=subprocess.DEVNULL)
                report['measurements'][f'{seconds}s-{mode}'] = json.loads(output.read_text())
                # Retain partial results if a subsequent long run fails.
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2) + '\n')
                print(f'Completed {seconds}s / {mode}', flush=True)
    print('Report:', args.output)


if __name__ == '__main__':
    main()

"""Repeat the pinned public JFK sample with a frozen reference; no download/mic."""
import argparse
import hashlib
import json
from pathlib import Path
import wave

SHA256 = '59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e'
REFERENCE = 'and so my fellow americans ask not what your country can do for you ask what you can do for your country'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--copies', type=int, required=True)
    parser.add_argument('--gap-seconds', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.copies <= 360 or not 0 <= args.gap_seconds <= 60:
        parser.error('Use 1–360 copies and 0–60 seconds between them')
    if hashlib.sha256(args.sample.read_bytes()).hexdigest() != SHA256:
        parser.error('Expected the pinned upstream public JFK fixture')
    with wave.open(str(args.sample), 'rb') as reader:
        if (reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) != (1, 2, 16000):
            parser.error('Expected 16 kHz mono 16-bit PCM')
        pcm = reader.readframes(reader.getnframes())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    with wave.open(str(args.output_dir / 'audio.wav'), 'wb') as writer:
        writer.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        for _ in range(args.copies):
            writer.writeframesraw(pcm + bytes(args.gap_seconds * 16000 * 2))
    reference = (' ' + REFERENCE) * args.copies
    (args.output_dir / 'reference.txt').write_text(reference, encoding='utf-8')
    manifest = {'kind': 'repeated-public', 'source_sha256': SHA256,
                'copies': args.copies, 'gap_seconds': args.gap_seconds,
                'reference_sha256': hashlib.sha256(reference.encode()).hexdigest()}
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()

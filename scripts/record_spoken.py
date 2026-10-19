"""Guided LOCAL speech collection: explicit opt-in SAVED AUDIO, never uploaded.

Requires Linux, ffmpeg's PulseAudio input, and an interactive terminal. Keep
corpora outside Git. References are fixed before recording/recognition. Ctrl+C
removes the unfinished take and retains accepted clips for an explicit retry.
"""
import argparse
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
from evaluate_spoken import load_manifest


def capture(destination, seconds):
    """Capture one bounded take; publish only a successful, sample-bearing WAV."""
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.wav', delete=False) as scratch:
        temporary = Path(scratch.name)
    process = None
    try:
        process = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                                    '-stats_period', '0.1', '-progress', 'pipe:1',
                                    '-f', 'pulse', '-i', 'default', '-t', str(seconds),
                                    '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(temporary)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print('Opening microphone; wait for Recording...', flush=True)
        deadline, progress, ready = time.monotonic() + seconds + 10, b'', False
        while process.poll() is None:
            if time.monotonic() > deadline:
                raise RuntimeError('Capture timed out')
            streams = [process.stdout, *([sys.stdin] if ready else [])]
            readable, _, _ = select.select(streams, [], [], .1)
            if process.stdout in readable:
                progress += os.read(process.stdout.fileno(), 4096)
                lines = progress.split(b'\n')
                progress = lines.pop()
                for line in lines:
                    if line.startswith(b'out_time_us=') and line[12:].isdigit() and int(line[12:]) > 0 and not ready:
                        print(f'Recording (maximum {seconds}s). Speak, then press Enter to finish:', flush=True)
                        ready = True
            if sys.stdin in readable:
                sys.stdin.readline()
                break
        _, errors = process.communicate(b'q\n' if process.poll() is None else None, timeout=10)
        if process.returncode or not ready:
            raise RuntimeError('Capture failed or no samples arrived: ' + errors.decode(errors='replace'))
        os.replace(temporary, destination)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        temporary.unlink(missing_ok=True)


def review_take(destination):
    """Human capture-quality review before ASR; never inspect recognition output."""
    while True:
        answer = input('[Enter] keep this take | p: play locally | r: record again | q: stop: ').strip().lower()
        if answer == '':
            return True
        if answer == 'r':
            return False
        if answer == 'q':
            raise KeyboardInterrupt
        if answer == 'p':
            if not shutil.which('ffplay'):
                print('ffplay is unavailable; use your local audio player, then keep or retry.')
            else:
                subprocess.run(['ffplay', '-nodisp', '-autoexit', '-loglevel', 'error', str(destination)],
                               check=True, timeout=40)


def display_prompt(case, index, total):
    """Separate delivery advice from the only text the speaker should read."""
    print(f"\n[{index}/{total}: {case['id']}]")
    if case.get('speaker_note'):
        print('Note (do not read aloud):', case['speaker_note'])
    print('Read aloud:', case.get('read_aloud', case['reference']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompts', type=Path, default=Path(__file__).resolve().parents[1] / 'tests/spoken_prompt_cases.json')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--consent-save-audio', action='store_true')
    parser.add_argument('--seconds', type=int, default=20, help='Maximum per prompt (1–30 seconds)')
    parser.add_argument('--cases', nargs='+', help='Optional subset of authored case IDs')
    parser.add_argument('--review', action='store_true', help='Offer local playback/retakes before accepting each clip')
    args = parser.parse_args()
    if not args.consent_save_audio:
        parser.error('This tool SAVES recordings; --consent-save-audio is required')
    if not sys.platform.startswith('linux') or not os.isatty(0) or not 1 <= args.seconds <= 30:
        parser.error('Use an interactive Linux terminal and a 1–30 second recording limit')
    prompts = load_manifest(args.prompts.resolve())
    cases = [case for case in prompts['cases'] if args.cases is None or case['id'] in args.cases]
    if not cases or (args.cases and set(args.cases) - {case['id'] for case in cases}):
        parser.error('Unknown/empty case selection')
    root = args.output_dir.resolve()
    old_mask = os.umask(0o077)
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o077:
            parser.error('Output directory must be owner-only (mode 0700) and owned by you')
        manifest = root / 'manifest.json'
        if manifest.exists():
            parser.error('Choose a new output directory; manifest already exists')
        selected = {'schema_version': 1, 'scope': 'Consented local human recordings; references fixed before recognition.',
                    'source_scope': prompts.get('scope', ''),
                    'cases': [{k: v for k, v in case.items() if k != '_audio'} for case in cases]}
        for case in cases:
            audio = (root / case['audio']).resolve()
            if root not in audio.parents or audio.exists() or (root / case['audio']).is_symlink():
                parser.error('Audio destinations must be new files inside the output directory')
        with manifest.open('x', encoding='utf-8') as target:
            json.dump(selected, target, indent=2, ensure_ascii=False)
            target.write('\n')
        print('LOCAL SAVED AUDIO. Close unrelated audio apps and check the default microphone.')
        print('Speak naturally. Retake only capture problems, not to chase recognition results.')
        for index, case in enumerate(cases, 1):
            destination = root / case['audio']
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            while True:
                display_prompt(case, index, len(cases))
                input('Press Enter when ready to record (Ctrl+C stops the session): ')
                capture(destination, args.seconds)
                print('Saved locally:', destination)
                if not args.review or review_take(destination):
                    break
                destination.unlink()
        print('\nCorpus manifest:', manifest)
        print('Collection finished. No audio uploaded; recognition has not run yet.')
    finally:
        os.umask(old_mask)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped. Completed takes remain local; an unfinished capture was discarded.')
        raise SystemExit(130)

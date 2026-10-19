"""Guided LOCAL human-speech collection; explicitly opt-in SAVED AUDIO.

Unlike the installed app, this developer tool writes microphone recordings.
Requires --consent-save-audio, ffmpeg, a PulseAudio-compatible default input and
an interactive terminal. Private files are owner-only, never uploaded, and must
stay outside git (use build-private-dictation/). No recognition runs while
recording; references must be fixed before looking at any model outputs.
"""
import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
from evaluate_spoken import load_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompts', type=Path, default=Path(__file__).resolve().parents[1] / 'tests/spoken_prompt_cases.json')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--consent-save-audio', action='store_true')
    parser.add_argument('--seconds', type=int, default=20, help='Maximum capture per prompt (1–30 seconds)')
    parser.add_argument('--cases', nargs='+', help='Optional subset of authored case IDs')
    args = parser.parse_args()
    if not args.consent_save_audio:
        parser.error('This tool SAVES recordings; --consent-save-audio is required')
    if not os.isatty(0) or not 1 <= args.seconds <= 30:
        parser.error('Use an interactive terminal and a 1–30 second recording limit')
    prompts = load_manifest(args.prompts.resolve())
    cases = [case for case in prompts['cases'] if args.cases is None or case['id'] in args.cases]
    if not cases or (args.cases and set(args.cases) - {case['id'] for case in cases}):
        parser.error('Unknown/empty case selection')
    root = args.output_dir.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest = root / 'manifest.json'
    # Never overwrite an existing corpus or silently change its references.
    if manifest.exists():
        parser.error('Choose a new output directory; manifest already exists')
    selected = {'schema_version': 1, 'scope': prompts.get('scope', ''), 'cases': []}
    for case in cases:
        selected['cases'].append({k: v for k, v in case.items() if k != '_audio'})
        audio = (root / case['audio']).resolve()
        if root not in audio.parents or audio.exists():
            parser.error('Audio destinations must be new files inside the output directory')
    old_mask = os.umask(0o077)
    try:
        with manifest.open('x', encoding='utf-8') as target:
            json.dump(selected, target, indent=2, ensure_ascii=False)
            target.write('\n')
        print('SAVED AUDIO session. Close unrelated audio apps; check the default microphone first.')
        print('References are now fixed. Say the displayed prompt naturally; do not chase a preferred ASR output.')
        for case in cases:
            print(f"\n[{case['id']}] {case.get('read_aloud', case['reference'])}")
            input('Press Enter when ready to record (Ctrl+C stops the session): ')
            destination = root / case['audio']
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.wav', delete=False) as scratch:
                temporary = Path(scratch.name)
            process = None
            try:
                process = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                                            '-stats_period', '0.1', '-progress', 'pipe:1',
                                            '-f', 'pulse', '-i', 'default', '-t', str(args.seconds),
                                            '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(temporary)],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print('Opening microphone; wait for Recording...', flush=True)
                deadline = time.monotonic() + args.seconds + 10
                progress = b''
                ready_to_speak = False
                while process.poll() is None:
                    if time.monotonic() > deadline:
                        raise RuntimeError('Capture timed out')
                    streams = [process.stdout]
                    if ready_to_speak:
                        streams.append(sys.stdin)
                    readable, _, _ = select.select(streams, [], [], .1)
                    if process.stdout in readable:
                        progress += os.read(process.stdout.fileno(), 4096)
                        lines = progress.split(b'\n')
                        progress = lines.pop()
                        for line in lines:
                            if line.startswith(b'out_time_us=') and line[12:].isdigit() and int(line[12:]) > 0:
                                if not ready_to_speak:
                                    print(f'Recording (maximum {args.seconds}s). Speak, then press Enter to finish:', flush=True)
                                    ready_to_speak = True
                    if sys.stdin in readable:
                        sys.stdin.readline()
                        break
                _, errors = process.communicate(b'q\n' if process.poll() is None else None, timeout=10)
                if process.returncode or not ready_to_speak:
                    raise RuntimeError('Capture failed or no samples arrived: ' + errors.decode(errors='replace'))
                os.replace(temporary, destination)
                print('Saved:', destination)
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.communicate()
                temporary.unlink(missing_ok=True)
    finally:
        os.umask(old_mask)
    print('\nCorpus manifest:', manifest)
    print('Listen for capture problems before evaluation. Do not change references after seeing model output.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped. Previously accepted recordings remain local; the unfinished clip was discarded.')
        raise SystemExit(130)

"""One-command private Linux dictation session: collect, replay, then score locally.

No audio or reports are uploaded. This developer tool SAVES audio with explicit
consent; the installed Mika CLI does not. A successful session is personal
validation, not a broad accuracy benchmark or permission to auto-submit prompts.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consent-save-audio', action='store_true')
    parser.add_argument('--probe', type=Path, default=ROOT / 'build-laptop/bin/mika-inference-test')
    parser.add_argument('--model', type=Path, default=Path.home() / '.local/share/mika/models/granite-speech-5.0-470m-turboctc-Q4_K_M.gguf')
    parser.add_argument('--cases', nargs='+', help='Optional short pilot, e.g. negation numbers hesitation')
    args = parser.parse_args()
    if not args.consent_save_audio:
        parser.error('Local saved recordings require --consent-save-audio; microphone has not been opened')
    if not sys.platform.startswith('linux') or not sys.stdin.isatty():
        parser.error('Run this guided session in a separate interactive Linux terminal')
    for path in (args.probe, args.model):
        if not path.is_file():
            parser.error(f'Missing prerequisite: {path}. Ask for the build/model setup before recording.')
    if not os.access(args.probe, os.X_OK) or not shutil.which('ffmpeg'):
        parser.error('An executable inference probe and ffmpeg with PulseAudio input are required')
    source = 'system default input'
    if shutil.which('pactl'):
        result = subprocess.run(['pactl', 'get-default-source'], capture_output=True, text=True, timeout=5)
        if result.returncode:
            parser.error('Cannot reach the audio server. Check PipeWire/PulseAudio before recording.')
        source = result.stdout.strip()
        if source.endswith('.monitor'):
            parser.error('Default input is a speaker-monitor device, not your microphone. Select your microphone in sound settings.')
    print('\nMIKA — PRIVATE GUIDED DICTATION CHECK\n')
    print('Input:', source)
    print('You control every recording: Enter to start, wait for Recording, speak, Enter to stop.')
    print('After each clip: Enter keeps it, p plays it locally, r retries capture, q stops.')
    print('Use your normal speaking voice. A mismatch is useful evidence, not your mistake.')
    print('Only read the shown prompts; avoid passwords or other private information.')
    print('Audio stays here in an owner-only ignored directory. We will review before deletion.')
    if input('\nReady with the correct microphone? [y/N] ').strip().lower() not in ('y', 'yes'):
        print('Cancelled; microphone was not opened.')
        return 130
    previous_mask = os.umask(0o077)
    try:
        private = ROOT / 'build-private-dictation'
        private.mkdir(mode=0o700, exist_ok=True)
        if private.stat().st_uid != os.geteuid() or private.stat().st_mode & 0o077 or private.is_symlink():
            parser.error('Private session parent must be your unlinked owner-only (0700) directory')
        ignored = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', str(private)], timeout=5)
        if ignored.returncode:
            parser.error('Private session directory is not Git-ignored; refusing to record')
        session = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=private))
        print('Private session:', session, flush=True)
        command = [sys.executable, str(ROOT / 'scripts/record_spoken.py'), '--consent-save-audio',
                   '--review', '--output-dir', str(session)]
        if args.cases:
            command += ['--cases', *args.cases]
        result = subprocess.run(command)
        if result.returncode:
            print('Session stopped. Accepted takes remain private; no recognition has run.')
            return result.returncode
        print('\nScoring raw and formatted recognition locally; no transcripts retained in the report.', flush=True)
        report = session / 'report.json'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/evaluate_spoken.py'), '--probe', str(args.probe.resolve()),
                                 '--model', str(args.model.resolve()), '--manifest', str(session / 'manifest.json'),
                                 '--output', str(report)])
        if report.exists():
            data = json.loads(report.read_text())
            print('\nCases needing manual review (a flag is not automatically a meaning error):')
            for case in data['cases']:
                flags = case['formatted'].get('critical_review_flags', [])
                status = ', '.join(flag['label'] for flag in flags) or ('no phrase flags' if case['formatted']['exit_code'] == 0 else 'recognition failed/no speech')
                print(f"  {case['id']}: {status}")
        print('\nFinished. Tell the assistant this session path:', session)
        print('Keep the private recordings until we compare fixes; nothing was uploaded or committed.')
        return result.returncode
    finally:
        os.umask(previous_mask)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nStopped. Any accepted clips remain private; no upload occurs.')
        raise SystemExit(130)

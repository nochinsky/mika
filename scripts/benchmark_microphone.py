"""Opt-in Linux PTY benchmark of the REAL CLI and default microphone.

Opens the microphone briefly, observes Listening, then cancels with Esc. Audio
stays in Mika's memory and is never saved/uploaded. No transcript is retained.
Launch-to-Listening is externally observed (includes scheduling/PTY observation).
Peak RSS is whole-child ru_maxrss from wait4, not sampled or incremental memory.
Requires an existing verified model; decline consent rather than download it.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import statistics
import subprocess
import termios
import time
from benchmark_common import cache_files, environment, evict_files


def measure(binary, listen_seconds, timeout=30):
    master, slave = pty.openpty()
    before = termios.tcgetattr(slave)
    process = None
    reaped = False
    observed = bytearray()
    transcript_bytes = 0
    listening_at = cancelled_at = None
    start = time.monotonic()
    try:
        def session():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        process = subprocess.Popen([str(binary)], stdin=slave, stderr=slave,
                                   stdout=subprocess.PIPE, preexec_fn=session)
        stdout = process.stdout.fileno()
        streams = {master, stdout}
        while True:
            now = time.monotonic()
            if now - start > timeout:
                raise RuntimeError('CLI timed out; no successful microphone timing')
            if listening_at is not None and cancelled_at is None and now - listening_at >= listen_seconds:
                os.write(master, b'\x1b')
                cancelled_at = time.monotonic()
            ready, _, _ = select.select(list(streams), [], [], .01)
            for fd in ready:
                data = os.read(fd, 65536)
                if not data:
                    streams.discard(fd)
                elif fd == stdout:
                    transcript_bytes += len(data)  # Deliberately discard text.
                else:
                    observed.extend(data)
                    if b'Download now?' in observed:
                        os.write(master, b'n')
                        raise RuntimeError('Model is missing; first install it with normal consent')
                    if listening_at is None and b'Listening ' in observed:
                        listening_at = time.monotonic()
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                reaped = True
                process.returncode = os.waitstatus_to_exitcode(status)
                # The child has closed stdout; drain any remaining bytes.
                transcript_bytes += len(process.stdout.read())
                if process.returncode != 130 or listening_at is None or cancelled_at is None:
                    raise RuntimeError(f'CLI failed before a measured cancellation (exit {process.returncode})')
                if transcript_bytes:
                    raise RuntimeError('Cancelled CLI unexpectedly wrote a transcript')
                if termios.tcgetattr(slave) != before:
                    raise RuntimeError('CLI did not restore terminal modes')
                return {'launch_to_listening_ms': (listening_at - start) * 1000,
                        'cancel_to_exit_ms': (time.monotonic() - cancelled_at) * 1000,
                        'listen_seconds': listen_seconds, 'peak_rss_kib': usage.ru_maxrss,
                        'audio_progress_observed': b'Listening 00:01' in observed,
                        'exit_code': process.returncode, 'stdout_bytes': transcript_bytes}
    finally:
        if process is not None:
            if not reaped:
                try:
                    os.kill(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                except ProcessLookupError:
                    process.wait()
            process.stdout.close()
        # Restore our private PTY even if the process was killed/timed out.
        termios.tcsetattr(slave, termios.TCSANOW, before)
        os.close(master)
        os.close(slave)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-microphone', action='store_true', help='Explicit consent; no audio is saved')
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--listen-seconds', type=float, default=1.2)
    parser.add_argument('--cache-mode', choices=('warm', 'evict'), default='warm')
    parser.add_argument('--model', type=Path, help='Actual default model path, for file-local eviction only')
    args = parser.parse_args()
    if not args.allow_microphone:
        parser.error('Microphone access requires --allow-microphone')
    if not 1 <= args.runs <= 10 or not .1 <= args.listen_seconds <= 5:
        parser.error('Use 1–10 runs with 0.1–5 seconds of microphone capture per run')
    if args.cache_mode == 'evict' and args.model is None:
        parser.error('--model is required for eviction; it does not override the CLI model location')
    report = {'scope': __doc__, 'environment': environment(), 'cache_mode': args.cache_mode,
              'cache_note': 'Normal caches' if args.cache_mode == 'warm' else
              'Best-effort file-local eviction, NOT guaranteed cold caches', 'runs': []}
    for _ in range(args.runs):
        if args.cache_mode == 'evict':
            evict_files(cache_files(args.binary, args.model))
        report['runs'].append(measure(args.binary.resolve(), args.listen_seconds))
    for field in ('launch_to_listening_ms', 'cancel_to_exit_ms', 'peak_rss_kib'):
        report['median_' + field] = statistics.median(row[field] for row in report['runs'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

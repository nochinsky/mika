"""Prepare the one bundled CPU Silero VAD; build-time only, no ASR downloads."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

REVISION = 'a9b2d61c20ae4ddf3644edb34969e8185a485448'
MODEL_FILE = 'silero-vad-v6.2-F32.gguf'
MODEL_BYTES = 1241056
MODEL_SHA256 = '0d871a800c420fdd5d1b17a3aea4296d1c39608f0ff4a9295eb76457eb1c88e6'
MODEL_URL = ('https://huggingface.co/handy-computer/silero-vad-v6.2-gguf/resolve/'
             + REVISION + '/' + MODEL_FILE)
LICENSE = Path(__file__).resolve().parents[1] / 'licenses/silero-vad-LICENSE.txt'


MAX_REDIRECTS = 10
PREPARE_TIMEOUT = 120


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # urllib's default handler drains redirect bodies without a size bound.
    # Return the response untouched so open_https can close it without reading.
    def http_error_302(self, req, fp, code, msg, headers):
        return fp

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def open_https(opener, url):
    for hop in range(MAX_REDIRECTS + 1):
        if urllib.parse.urlsplit(url).scheme.lower() != 'https':
            raise ValueError('HTTPS required, including redirects')
        response = opener.open(url, timeout=30)
        if response.status not in (301, 302, 303, 307, 308):
            return response
        try:
            location = response.headers.get('Location')
        finally:
            response.close()
        if not location:
            raise ValueError('Redirect has no Location')
        if hop == MAX_REDIRECTS:
            raise ValueError('Too many speech asset redirects')
        url = urllib.parse.urljoin(url, location)


def verified(path, size, digest):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        return False
    sha = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(65536), b''):
            sha.update(block)
    return sha.hexdigest() == digest


def fetch(cache, name, spec):
    url, size, digest = spec
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / name
    if verified(destination, size, digest):
        return destination
    print('Fetching pinned speech asset:', name, flush=True)
    opener = urllib.request.build_opener(NoRedirect())
    deadline = time.monotonic() + PREPARE_TIMEOUT
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
        temporary = Path(output.name)
        try:
            with open_https(opener, url) as response:
                if response.status != 200:
                    raise ValueError('Unexpected HTTP response')
                total = 0
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Speech asset download deadline exceeded')
                    data = response.read(min(65536, size + 1 - total))
                    if not data:
                        break
                    total += len(data)
                    if total > size:
                        raise ValueError('Speech asset exceeds expected size')
                    output.write(data)
            output.flush()
            if not verified(temporary, size, digest):
                raise ValueError('Speech asset size/SHA-256 mismatch: ' + name)
            output.close()
            os.replace(temporary, destination)
        finally:
            output.close()
            temporary.unlink(missing_ok=True)
    return destination


def prepare(stage):
    stage.mkdir(parents=True, exist_ok=True)
    model = fetch(stage / 'downloads', MODEL_FILE, (MODEL_URL, MODEL_BYTES, MODEL_SHA256))
    # Build a complete payload before publication; cached files are never trusted
    # without verification. Only this model and its combined license/notice ship.
    temporary = Path(tempfile.mkdtemp(dir=stage, prefix='payload-'))
    previous = temporary / 'previous-payload'
    published = False
    try:
        payload = temporary / 'payload'
        payload.mkdir()
        shutil.copyfile(model, payload / MODEL_FILE)
        shutil.copyfile(LICENSE, payload / 'LICENSE.txt')
        destination = stage / 'payload'
        had_previous = destination.exists() or destination.is_symlink()
        if had_previous:
            destination.rename(previous)
        try:
            payload.rename(destination)
        except OSError:
            if had_previous:
                previous.rename(destination)
            raise
        published = True
    finally:
        # If even rollback fails, retain the backup at the path in that error.
        if published or not (previous.exists() or previous.is_symlink()):
            shutil.rmtree(temporary)
    return destination


def prepare_bounded(stage, timeout=PREPARE_TIMEOUT):
    # A socket timeout is only an inactivity limit. A separate process bounds
    # even DNS, headers, and buffered/trickled reads; run kills and reaps it on
    # timeout, so no background thread can continue writing after failure.
    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                    '--stage', str(stage)], check=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print('Pinned Silero VAD ready:', prepare(args.stage), flush=True)
    else:
        prepare_bounded(args.stage)


if __name__ == '__main__':
    main()

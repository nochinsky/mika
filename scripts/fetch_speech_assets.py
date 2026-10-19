"""Prepare the one bundled CPU Silero VAD; build-time only, no ASR downloads."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.request

REVISION = 'a9b2d61c20ae4ddf3644edb34969e8185a485448'
MODEL_FILE = 'silero-vad-v6.2-F32.gguf'
MODEL_BYTES = 1241056
MODEL_SHA256 = '0d871a800c420fdd5d1b17a3aea4296d1c39608f0ff4a9295eb76457eb1c88e6'
MODEL_URL = ('https://huggingface.co/handy-computer/silero-vad-v6.2-gguf/resolve/'
             + REVISION + '/' + MODEL_FILE)
LICENSE = Path(__file__).resolve().parents[1] / 'licenses/silero-vad-LICENSE.txt'


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith('https://'):
            raise ValueError('Refusing a non-HTTPS redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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
    opener = urllib.request.build_opener(HTTPSOnly())
    deadline = time.monotonic() + 120
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
        temporary = Path(output.name)
        try:
            with opener.open(url, timeout=30) as response:
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
    with tempfile.TemporaryDirectory(dir=stage, prefix='payload-') as temporary:
        payload = Path(temporary) / 'payload'
        payload.mkdir()
        shutil.copyfile(model, payload / MODEL_FILE)
        shutil.copyfile(LICENSE, payload / 'LICENSE.txt')
        destination = stage / 'payload'
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)
        payload.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, type=Path)
    args = parser.parse_args()
    print('Pinned Silero VAD ready:', prepare(args.stage), flush=True)


if __name__ == '__main__':
    main()

"""Shared build-only asset I/O: bounded HTTPS, verified cache and payload rollback.

One writer per staging directory. Handled failures preserve the previous payload;
a crash/forced kill can leave scratch or recovery directories for inspection.
Nothing here runs in installed Mika or handles dictated audio/text.
"""
from contextlib import contextmanager
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

MAX_REDIRECTS = 10
DOWNLOAD_TIMEOUT = 120


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # urllib's default redirect handler drains response bodies without a bound.
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
            raise ValueError('Too many asset redirects')
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
    print('Fetching pinned asset:', name, flush=True)
    opener = urllib.request.build_opener(NoRedirect())
    deadline = time.monotonic() + DOWNLOAD_TIMEOUT
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
        temporary = Path(output.name)
        try:
            with open_https(opener, url) as response:
                if response.status != 200:
                    raise ValueError('Unexpected HTTP response')
                total = 0
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Asset download deadline exceeded')
                    data = response.read(min(65536, size + 1 - total))
                    if not data:
                        break
                    total += len(data)
                    if total > size:
                        raise ValueError('Asset exceeds expected size')
                    output.write(data)
            output.flush()
            if not verified(temporary, size, digest):
                raise ValueError('Asset size/SHA-256 mismatch: ' + name)
            output.close()
            os.replace(temporary, destination)
        finally:
            output.close()
            temporary.unlink(missing_ok=True)
    return destination


@contextmanager
def payload_transaction(stage):
    """Prepare a complete payload, then swap it with recoverable old contents."""
    temporary = Path(tempfile.mkdtemp(dir=stage, prefix='payload-'))
    previous = temporary / 'previous-payload'
    published = False
    try:
        payload = temporary / 'payload'
        payload.mkdir()
        yield payload
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
        # A failed rollback must not erase the only remaining previous payload.
        if published or not (previous.exists() or previous.is_symlink()):
            shutil.rmtree(temporary)


def run_bounded(script, stage, timeout, arguments=()):
    # Socket deadlines cannot bound DNS/trickled reads. The worker performs all
    # preparation in-process; run kills/reaps it, with no converter child left.
    subprocess.run([sys.executable, str(Path(script).resolve()), '--worker',
                    '--stage', str(stage), *arguments], check=True, timeout=timeout)

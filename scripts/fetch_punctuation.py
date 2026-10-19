"""Build-time pinned assets for the fixed English FullStop formatter.

Builds fetch original weights and quantize locally with pinned development
packages. No Python runtime, conversion, downloads or uploads during dictation.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

VERSION = '1.13.8'  # Only the ORT binaries are used from this CPU/no-TTS SDK.
RAW = 'https://raw.githubusercontent.com/'
MODEL = 'https://huggingface.co/1-800-BAD-CODE/punctuation_fullstop_truecase_english/resolve/b26fd1c40e88678859048898218ea4edcc24c84a/'
ORT = RAW + 'microsoft/onnxruntime/v1.28.2/'
SP = RAW + 'google/sentencepiece/31646a467d2051eb904e0b45de3a73e91fe1c1e3/'
SOURCE_MODEL = (MODEL + 'punct_cap_seg_en.onnx', 209532928, 'dd922d459da618cd324280889740608b76fb3e9e61d3f402291be1251f91421b')
QUANTIZED = (52883510, 'd69b2df2db21c177b8ea9086e2324796176fb5a28fa8893f9df11b79bf3fc3ec')
ARTIFACTS = {
    'sp.model': (MODEL + 'spe_32k_lc_en.model', 587902, '9e86d0263de80b3b68327a21f5350c8cdf846e4c4400253c9baf05e3d44871c3'),
    'fullstop-model-card.md': (MODEL + 'README.md', 16830, '47e853ebf1ed795445914383e165ad37cac94156bebe2e723865b721ace80831'),
    'fullstop-config.yaml': (MODEL + 'config.yaml', 302, '002ea72d7ef44a6d547b9ca251d6201c20bcf1e0d02e8bb2890141d92b8bfc8e'),
    'onnxruntime-LICENSE.txt': (ORT + 'LICENSE', 1073, '2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c'),
    'onnxruntime-ThirdPartyNotices.txt': (ORT + 'ThirdPartyNotices.txt', 325054, '0e07b95f3a8d6230037707c5c4a2b554d12c4cb67369669ac255635528ffcee2'),
    'sentencepiece-LICENSE.txt': (SP + 'LICENSE', 11358, 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'),
    'sentencepiece-protobuf-LICENSE.txt': (SP + 'third_party/protobuf-lite/LICENSE', 1732, '6e5e117324afd944dcf67f36cf329843bc1a92229a8cd9bb573d7a83130fea7d'),
    'sentencepiece-absl-LICENSE.txt': (SP + 'third_party/absl/LICENSE', 11365, 'd3e2f59e1d71176dfdb555ece6a41f7a5aa0f52ff21211010ace314f57695f6b'),
    'sentencepiece-darts-LICENSE.txt': (SP + 'third_party/darts_clone/LICENSE', 1481, '155f59997298ee336602c49f9c1110f268ac394ca2197eb02647a3555935ad52'),
    'sentencepiece-esaxx-LICENSE.txt': (SP + 'third_party/esaxx/LICENSE', 1112, '7c28553d1d3312d65fe309f76a22ebaf33a3d76c8c1e3b98a88ee4654ecb53db'),
}
HEADERS = {
    'onnxruntime_c_api.h': (394991, 'b69a133143c0da61782b2b02cc8a620d21ac139231fd211719776d10385135c1'),
    'onnxruntime_cxx_api.h': (168928, 'c6bf005e4063b7db911d0a6b030452bcb9d4fc5e87530a39d94c4a5fcd311b61'),
    'onnxruntime_cxx_inline.h': (157610, '97f960b1bc4a372918893ef4c77102dee725ccfce0d76607f4570b03e7e28325'),
    'onnxruntime_float16.h': (17991, '88b242845d25981633a0bbd1c148e273cf8bfb016ea3f57c4af41a06530f72b0'),
    'onnxruntime_ep_c_api.h': (152985, 'db86df0f846b8d3bdbf429a5c76c5805293196575ca3c475878612591cd18e51'),
    'onnxruntime_error_code.h': (2775, '5ce3b054e798eced8d14f5b86e98692fd33470463f96194ce0700a2d53dd8721'),
}
SDK = {
    'macos': ('osx-arm64-shared-no-tts-lib', 8292111, 'f3e0cbd86cc3f38dad30c97921b40e9a8bcc6f2c943777eb76ad77176993e417', ['libonnxruntime.dylib']),
    'linux': ('linux-x64-shared-no-tts-lib', 9249201, 'bf2d998c8b07012cd5098f3b92673bc1333fd9b927767d7cb664be8190d8bc0b', ['libonnxruntime.so']),
    'windows': ('win-x64-shared-MT-Release-no-tts-lib', 7536080, 'a1253e665c4f236119c443c8932a8acfca32a546c78c05962d483c9a0eae21b7', ['onnxruntime.dll', 'onnxruntime_providers_shared.dll', 'onnxruntime.lib']),
}


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith('https://'):
            raise ValueError('Refusing a non-HTTPS redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verified(path, size, digest):
    if not path.is_file() or path.stat().st_size != size:
        return False
    sha = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(65536), b''):
            sha.update(block)
    return sha.hexdigest() == digest


def fetch(cache, name, spec):
    url, size, digest = spec
    destination = cache / name
    if verified(destination, size, digest):
        return destination
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    print('Fetching pinned punctuation asset:', name, flush=True)
    opener = urllib.request.build_opener(HTTPSOnly())
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
        temporary = Path(output.name)
        try:
            with opener.open(url, timeout=60) as response:
                if response.status != 200:
                    raise ValueError('Unexpected HTTP response')
                total = 0
                while True:
                    data = response.read(65536)
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


def quantized_model(cache):
    destination = cache / 'model.int8.onnx'
    if verified(destination, *QUANTIZED):
        return destination
    source = fetch(cache, 'fullstop.fp32.onnx', SOURCE_MODEL)
    with tempfile.NamedTemporaryFile(dir=cache, suffix='.onnx', delete=False) as output:
        temporary = Path(output.name)
    try:
        subprocess.run([sys.executable, str(Path(__file__).with_name('quantize_punctuation.py')),
                        str(source), str(temporary)], check=True, timeout=300)
        if not verified(temporary, *QUANTIZED):
            raise ValueError('Derived FullStop model size/SHA-256 mismatch; refusing to publish it')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--platform', choices=SDK, required=True)
    args = parser.parse_args()
    cache = args.stage / 'downloads'
    include = args.stage / 'include'
    for directory in (cache, include):
        directory.mkdir(parents=True, exist_ok=True)
    # Publish a fresh payload only after all downloads/conversion succeed. Do not
    # retain the previous experimental backend's unused libraries or vocabulary.
    with tempfile.TemporaryDirectory(dir=args.stage, prefix='payload-') as temporary:
        payload = Path(temporary) / 'payload'
        (payload / 'licenses').mkdir(parents=True)
        shutil.copyfile(quantized_model(cache), payload / 'model.int8.onnx')
        for name, spec in ARTIFACTS.items():
            target = payload / name if name == 'sp.model' else payload / 'licenses' / name
            shutil.copyfile(fetch(cache, name, spec), target)
        # Standard Apache-2.0 text, retained under the model's own filename too.
        shutil.copyfile(payload / 'licenses/sentencepiece-LICENSE.txt', payload / 'licenses/fullstop-LICENSE.txt')
        shutil.copyfile(Path(__file__).resolve().parents[1] / 'licenses/fullstop-NOTICE.txt',
                        payload / 'licenses/fullstop-NOTICE.txt')
        for name, (size, digest) in HEADERS.items():
            url = ORT + 'include/onnxruntime/core/session/' + name
            shutil.copyfile(fetch(cache, name, (url, size, digest)), include / name)
        variant, size, digest, libraries = SDK[args.platform]
        root = 'sherpa-onnx-v' + VERSION + '-' + variant
        name = root + '.tar.bz2'
        url = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/v' + VERSION + '/' + name
        archive = fetch(cache, name, (url, size, digest))
        with tarfile.open(archive, 'r:bz2') as bundle:
            for library in libraries:
                member = bundle.getmember(root + '/lib/' + library)
                if not member.isfile() or member.size > 50000000:
                    raise ValueError('Invalid runtime archive member')
                target = include / library if library.endswith('.lib') else payload / library
                with bundle.extractfile(member) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
        destination = args.stage / 'payload'
        if destination.exists():
            shutil.rmtree(destination)
        payload.rename(destination)
    print('Pinned FullStop assets ready:', args.stage / 'payload', flush=True)


if __name__ == '__main__':
    main()

"""Developer-only, pinned assets for the unreleased punctuation prototype.

Invoked only by explicit MIKA_EXPERIMENTAL_PUNCTUATION=ON. No pip packages.
The CLI itself never downloads punctuation assets or sends text over a network.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

VERSION = '1.13.8'
MIRROR = 'https://huggingface.co/jiangzhuo9357/edge-punct-casing-en-onnx/resolve/a0897f6d38cc6f60ac9b9f807a31f7033d1fbc89/'
RAW = 'https://raw.githubusercontent.com/'
ARTIFACTS = {
    'model.int8.onnx': (MIRROR + 'model.int8.onnx', 7490500, '9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e'),
    'bpe.vocab': (MIRROR + 'bpe.vocab', 149430, 'e118b7ad88c54db562517df49e1cffd4836d166c34fb190fd311d7f34eb238f5'),
    'c-api.h': (RAW + 'k2-fsa/sherpa-onnx/v1.13.8/sherpa-onnx/c-api/c-api.h', 167657, '2a1b95084be8fd1deb3228fcad2fd3f7f0258b64582f7402281ec174c7b7f4ce'),
    'sherpa-LICENSE.txt': (RAW + 'k2-fsa/sherpa-onnx/v1.13.8/LICENSE', 11358, 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'),
    'edge-LICENSE.txt': (RAW + 'frankyoujian/Edge-Punct-Casing/c154bf777427f4549dfb56a0e9f696aae6136616/LICENSE', 11357, 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4'),
    'onnxruntime-LICENSE.txt': (RAW + 'microsoft/onnxruntime/v1.28.2/LICENSE', 1073, '2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c'),
    'onnxruntime-ThirdPartyNotices.txt': (RAW + 'microsoft/onnxruntime/v1.28.2/ThirdPartyNotices.txt', 325054, '0e07b95f3a8d6230037707c5c4a2b554d12c4cb67369669ac255635528ffcee2'),
    # The SDK contains more than the punctuation implementation. Retain its
    # no-TTS dependency notices too; do not mistake Apache-2.0 for the whole SDK.
    'ssentencepiece-LICENSE.txt': (RAW + 'pkufool/simple-sentencepiece/v0.7/LICENSE', 11357, 'c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4'),
    'ssentencepiece-darts-source.h': (RAW + 'pkufool/simple-sentencepiece/v0.7/ssentencepiece/csrc/darts.h', 53998, 'a0ff15abf69e2651dedef5acacf474b7b8d20ace8cd5dd79dd201e99ccfee91d'),
    'ssentencepiece-threadpool-source.h': (RAW + 'pkufool/simple-sentencepiece/v0.7/ssentencepiece/csrc/threadpool.h', 3255, 'a0737647480c4fbab218b3540b4be0cb35edf9b4e869e275f56f79f0d25d2830'),
    'kaldi-decoder-LICENSE.txt': (RAW + 'k2-fsa/kaldi-decoder/v0.3.0/LICENSE', 11358, 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'),
    'kaldi-native-fbank-LICENSE.txt': (RAW + 'csukuangfj/kaldi-native-fbank/v1.22.3/LICENSE', 11358, 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'),
    'kaldifst-LICENSE.txt': (RAW + 'k2-fsa/kaldifst/v1.8.0/LICENSE', 11728, 'a682d6efd1ee5dee08a8e405c233c2c198ea70ae0718129daa83ab58cfe31c5d'),
    'openfst-COPYING.txt': (RAW + 'csukuangfj/openfst/v1.8.5-2026-07-09/COPYING', 559, '4300529197035fd3452350718a0b8cee984e9412c9932d7f35fcde849fc97a4b'),
    'kissfft-COPYING.txt': (RAW + 'mborgerding/kissfft/febd4caeed32e33ad8b2e0bb5ea77542c40f18ec/COPYING', 246, 'a2840585f8411be8e6826a31ef15ae65c950bd74a2437a73b013398a934ad0c6'),
    'kissfft-BSD-3-Clause.txt': (RAW + 'mborgerding/kissfft/febd4caeed32e33ad8b2e0bb5ea77542c40f18ec/LICENSES/BSD-3-Clause', 1830, '4d6bcab46f27d6d0c878e8305d4bdcfe040d52bf6656b9771f04c9fb9902c0ed'),
    'hclust-LICENSE.txt': (RAW + 'csukuangfj/hclust-cpp/2026-02-25/LICENSE', 1483, 'e361d842da1d290351860ad6dcce2673a1e42e4f873a3ae1ff4eb92c6adaa882'),
    'json-LICENSE.txt': (RAW + 'nlohmann/json/v3.12.0/LICENSE.MIT', 1076, '46a65cffd1ea955132d95a8dd921640714a8d6b537d2e4e482d31145ae95b603'),
    'eigen-COPYING.MPL2.txt': ('https://gitlab.com/libeigen/eigen/-/raw/5.0.1/COPYING.MPL2', 16727, '66a3107d5ad6a058aab753eaac2047ccb2ed0e39465dd0fe5844da3e300d5172'),
}
SDK = {
    'linux': ('linux-x64-shared-no-tts-lib', 9249201, 'bf2d998c8b07012cd5098f3b92673bc1333fd9b927767d7cb664be8190d8bc0b', ['libonnxruntime.so', 'libsherpa-onnx-c-api.so']),
    'windows': ('win-x64-shared-MT-Release-no-tts-lib', 7536080, 'a1253e665c4f236119c443c8932a8acfca32a546c78c05962d483c9a0eae21b7', ['onnxruntime.dll', 'onnxruntime_providers_shared.dll', 'sherpa-onnx-c-api.dll']),
}


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith('https://'):
            raise ValueError('Refusing a non-HTTPS redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verified(path, size, digest):
    return path.is_file() and path.stat().st_size == size and hashlib.sha256(path.read_bytes()).hexdigest() == digest


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
            output.close()  # Windows cannot unlink an open failed download.
            temporary.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--platform', choices=SDK, required=True)
    args = parser.parse_args()
    cache = args.stage / 'downloads'
    payload = args.stage / 'payload'
    include = args.stage / 'include'
    for directory in [cache, payload, include, payload / 'licenses']:
        directory.mkdir(parents=True, exist_ok=True)
    for name, spec in ARTIFACTS.items():
        src = fetch(cache, name, spec)
        target = include / name if name == 'c-api.h' else payload / name if name in ('model.int8.onnx', 'bpe.vocab') else payload / 'licenses' / name
        shutil.copyfile(src, target)
    variant, size, digest, libraries = SDK[args.platform]
    root = 'sherpa-onnx-v' + VERSION + '-' + variant
    name = root + '.tar.bz2'
    url = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/v' + VERSION + '/' + name
    archive = fetch(cache, name, (url, size, digest))
    with tarfile.open(archive, 'r:bz2') as bundle:
        # Never extract paths/links from the archive. Copy only exact regular files.
        for library in libraries:
            member = bundle.getmember(root + '/lib/' + library)
            if not member.isfile() or member.size > 50000000:
                raise ValueError('Invalid runtime archive member')
            with bundle.extractfile(member) as src, (payload / library).open('wb') as dst:
                shutil.copyfileobj(src, dst)
    print('Pinned prototype assets ready:', payload, flush=True)


if __name__ == '__main__':
    main()

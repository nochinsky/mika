"""Create a relocatable release archive from cmake --install output."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tarfile
import tempfile
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--stage', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--platform', choices=['linux', 'windows', 'macos'], required=True)
parser.add_argument('--version', required=True)
parser.add_argument('--dependencies', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
source = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / 'mika'
    (root / 'bin').mkdir(parents=True)
    executable = 'mika.exe' if args.platform == 'windows' else 'mika'
    for binary in (args.stage / 'bin').iterdir():
        if binary.name == executable or (args.platform == 'windows' and binary.suffix.lower() == '.dll'):
            shutil.copy2(binary, root / 'bin' / binary.name)
    if not (root / 'bin' / executable).is_file():
        raise SystemExit('Missing Mika executable in install staging directory')
    if args.platform == 'linux':
        (root / 'lib').mkdir()
        for library in (args.stage / 'lib').glob('*.so*'):
            shutil.copy2(library, root / 'lib' / library.name, follow_symlinks=False)
        if not list((root / 'lib').glob('*ggml-cpu*')):
            raise SystemExit('Missing CPU dispatch modules in installed package')
    # Keep the existing build-prepared payload, not a second model distribution
    # mechanism. Reject accidental private inputs/build files before copying it.
    punctuation = args.stage / 'bin' / 'punctuation'
    required = {'model.int8.onnx', 'sp.model'} | (
        {'mika-fullstop.dll', 'onnxruntime.dll', 'onnxruntime_providers_shared.dll'}
        if args.platform == 'windows' else
        {'libmika-fullstop.dylib', 'libonnxruntime.dylib'} if args.platform == 'macos' else
        {'libmika-fullstop.so', 'libonnxruntime.so'})
    if not punctuation.is_dir() or not (punctuation / 'licenses').is_dir():
        raise SystemExit('Missing installed formatting payload/notices')
    actual = {item.name for item in punctuation.iterdir() if item.is_file()}
    if actual != required or any(item.is_dir() and item.name != 'licenses' for item in punctuation.iterdir()):
        raise SystemExit('Incomplete or unexpected files in formatting payload')
    if any(not item.is_file() or item.is_symlink() or item.suffix not in {'.txt', '.md', '.yaml'}
           for item in (punctuation / 'licenses').iterdir()):
        raise SystemExit('Unexpected files in formatting notices')
    shutil.copytree(punctuation, root / 'bin' / 'punctuation')
    for filename in ['LICENSE', 'README.md', 'CONTRIBUTING.md', 'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(source / filename, root / filename)
    shutil.copytree(source / 'licenses', root / 'licenses')
    shutil.copytree(source / 'docs', root / 'docs')
    if args.dependencies:
        for dependency in args.dependencies.iterdir():
            if not dependency.is_dir():
                continue
            for name in ['copyright', 'NOTICE', 'NOTICE.txt', 'LICENSE', 'LICENSE.txt']:
                notice = dependency / name
                if notice.is_file():
                    target = root / 'licenses' / 'dependencies' / dependency.name
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(notice, target / name)
    (root / 'VERSION').write_text(args.version + '\n')
    if args.platform != 'windows':
        archive = args.output / ('mika-macos-arm64.tar.gz' if args.platform == 'macos' else 'mika-linux-x86_64.tar.gz')
        with tarfile.open(archive, 'w:gz') as bundle:
            bundle.add(root, arcname='mika')
    else:
        archive = args.output / 'mika-windows-x86_64.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for item in sorted(root.rglob('*')):
                if item.is_file():
                    bundle.write(item, item.relative_to(root.parent).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    Path(str(archive) + '.sha256').write_text(f'{digest}  {archive.name}\n')
    print(f'{archive}: {archive.stat().st_size} bytes; SHA-256 {digest}')

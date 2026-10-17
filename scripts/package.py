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
parser.add_argument('--platform', choices=['linux', 'windows'], required=True)
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
    for filename in ['LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(source / filename, root / filename)
    shutil.copytree(source / 'licenses', root / 'licenses')
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
    if args.platform == 'linux':
        archive = args.output / 'mika-linux-x86_64.tar.gz'
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

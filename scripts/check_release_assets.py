"""Offline publication gate: require all three platform archives and checksums."""
import argparse
import hashlib
from pathlib import Path
import re
import tarfile
import zipfile

ARCHIVES = ('mika-linux-x86_64.tar.gz', 'mika-windows-x86_64.zip', 'mika-macos-arm64.tar.gz')
MAX_ARCHIVE_BYTES = 268435456  # Match installer transfer limits.


def validate(directory, version):
    if not re.fullmatch(r'v\d+\.\d+\.\d+', version):
        raise ValueError('Expected an immutable vX.Y.Z release tag')
    expected = set(ARCHIVES) | {name + '.sha256' for name in ARCHIVES}
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError('Release requires exactly three platform archives and their checksums')
    identities = {}
    for name in ARCHIVES:
        archive, checksum = directory / name, directory / (name + '.sha256')
        if any(path.is_symlink() or not path.is_file() for path in (archive, checksum)):
            raise ValueError('Release assets must be regular, unlinked files')
        if not 0 < archive.stat().st_size <= MAX_ARCHIVE_BYTES or checksum.stat().st_size > 4096:
            raise ValueError('Release asset exceeds installer limits')
        identity = checksum.read_text(encoding='ascii').strip()
        match = re.fullmatch(r'([a-f0-9]{64})  ' + re.escape(name), identity)
        digest = hashlib.sha256()
        with archive.open('rb') as source:
            for block in iter(lambda: source.read(1048576), b''):
                digest.update(block)
        if not match or digest.hexdigest() != match[1]:
            raise ValueError('Release checksum mismatch: ' + name)
        # Read only the small VERSION member; never extract/run cross-platform code.
        if name.endswith('.zip'):
            with zipfile.ZipFile(archive) as bundle:
                members = [item for item in bundle.infolist() if item.filename == 'mika/VERSION']
                if len(members) != 1 or members[0].file_size > 128:
                    raise ValueError('Missing/ambiguous release VERSION')
                embedded = bundle.read(members[0])
        else:
            with tarfile.open(archive, 'r:gz') as bundle:
                members = [item for item in bundle.getmembers() if item.name == 'mika/VERSION']
                if len(members) != 1 or not members[0].isfile() or members[0].size > 128:
                    raise ValueError('Missing/ambiguous release VERSION')
                with bundle.extractfile(members[0]) as source:
                    embedded = source.read(129)
        # Older Windows packages use native CRLF. Accept exactly one LF/CRLF,
        # not arbitrary whitespace, missing newlines or a different tag.
        if embedded not in (version.encode('ascii') + b'\n', version.encode('ascii') + b'\r\n'):
            raise ValueError('Archive VERSION does not match release tag: ' + name)
        identities[name] = digest.hexdigest()
    return identities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    identities = validate(args.directory, args.version)
    for name, digest in identities.items():
        print(digest, name)
    print('PASS: all three platform archives have matching release versions and checksums')


if __name__ == '__main__':
    main()

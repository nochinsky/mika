"""CI validation of installed libraries and installers; never records microphone audio."""
import argparse
import hashlib
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--stage', type=Path, required=True)
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--model', type=Path, required=True)
parser.add_argument('--sample', type=Path, required=True)
parser.add_argument('--installer-fixture', type=Path)
args = parser.parse_args()
source = Path(__file__).resolve().parents[1]
args.stage = args.stage.resolve()
args.archive = args.archive.resolve()
windows = os.name == 'nt'
exe = '.exe' if windows else ''
version = re.search(r'project\(mika VERSION ([^ ]+)', (source / 'CMakeLists.txt').read_text()).group(1)
expected_version = 'mika ' + version

def run(command, **kwargs):
    result = subprocess.run([str(x) for x in command], capture_output=True, timeout=120, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{command}\n{result.stdout.decode(errors="replace")}\n{result.stderr.decode(errors="replace")}')
    return result.stdout.decode(errors='replace')

assert run([args.stage / 'bin' / ('mika' + exe), '--version']).strip() == expected_version
# This installed probe has the same RPATH/DLL lookup location as the real app.
text = run([args.stage / 'bin' / ('mika-inference-test' + exe), args.model, args.sample])
assert 'ask not what your country can do for you' in text, text

if not windows:
    for binary in [args.stage / 'bin/mika', *(args.stage / 'lib').glob('*.so*')]:
        output = run(['ldd', binary])
        assert 'not found' not in output, output
        # Release dependencies must not require another distribution's curl/crypto ABI.
        for library in ['libcurl.so', 'libcrypto.so', 'libssl.so', 'libz.so']:
            assert library not in output, output
    with tempfile.TemporaryDirectory(prefix='mika release install ') as directory:
        env = {**os.environ, 'HOME': directory, 'XDG_DATA_HOME': str(Path(directory) / 'data'),
               'SHELL': '/bin/bash', 'MIKA_ARCHIVE_PATH': str(args.archive)}
        run(['bash', source / 'install.sh'], env=env)
        installed = Path(directory) / '.local/bin/mika'
        assert run([installed, '--version']).strip() == expected_version
        # Validate CPU loading after a genuine relocation of the installed archive.
        binary_dir = Path(directory) / 'data/mika/app/bin'
        probe = binary_dir / 'mika-inference-test'
        shutil.copy2(args.stage / 'bin/mika-inference-test', probe)
        assert 'ask not what your country' in run([probe, args.model, args.sample])
else:
    # This integration check is for a disposable native CI runner, not a user's PC.
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Windows installer integration must run in disposable GitHub Actions')
    root = Path(os.environ['LOCALAPPDATA']) / 'Mika/app'
    if root.exists():
        raise RuntimeError('Expected a clean Windows runner without an existing Mika installation')
    # PowerShell 7 sanitizes PSModulePath when launching Windows PowerShell 5.1
    # directly. A Python intermediary must do the same, or 5.1 finds PS7-only
    # module versions instead of its own inbox Get-FileHash/Expand-Archive.
    env = {key: value for key, value in os.environ.items() if key.upper() != 'PSMODULEPATH'}
    env['MIKA_ARCHIVE_PATH'] = str(args.archive)
    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', source / 'install.ps1']
    assert args.installer_fixture, 'Windows requires a fake old-release executable for transaction tests'
    with tempfile.TemporaryDirectory() as directory:
        old = Path(directory) / 'old.zip'
        with zipfile.ZipFile(old, 'w') as bundle:
            bundle.write(args.installer_fixture, 'mika/bin/mika.exe')
            bundle.writestr('mika/VERSION', 'v0.0.0\n')
        Path(str(old) + '.sha256').write_text(hashlib.sha256(old.read_bytes()).hexdigest() + '  old.zip\n')
        assert 'Installed Mika 0.0.0' in run(command, env={**env, 'MIKA_ARCHIVE_PATH': str(old)})
        models = root.parent / 'models'
        models.mkdir(exist_ok=True)
        marker = models / 'installer-preserve-test'
        marker.write_text('keep model data')
        assert 'Updated Mika 0.0.0 -> ' + version in run(command, env=env)
        before = (root / 'bin/mika.exe').read_bytes()
        # Corrupt checksums must not disturb a working installation.
        bad = Path(directory) / 'bad.zip'
        shutil.copyfile(args.archive, bad)
        Path(str(bad) + '.sha256').write_text('0' * 64 + '  bad.zip\n')
        failure = subprocess.run([str(x) for x in command], env={**env, 'MIKA_ARCHIVE_PATH': str(bad)}, capture_output=True, timeout=60)
        assert failure.returncode != 0
        assert (root / 'bin/mika.exe').read_bytes() == before
        # A binary that starts before the move but fails afterward must roll back.
        failure = subprocess.run([str(x) for x in command], env={**env, 'MIKA_ARCHIVE_PATH': str(old),
                                 'MIKA_INSTALL_FIXTURE_FAIL_FINAL': '1'}, capture_output=True, timeout=60)
        assert failure.returncode != 0, failure.stdout
        assert (root / 'bin/mika.exe').read_bytes() == before
        assert not list(root.parent.glob('.install.*'))
        # A move can finish and then be interrupted before the next statement.
        wrapper = Path(directory) / 'interrupt-swap.ps1'
        wrapper.write_text(r'''param([string]$Installer)
$ErrorActionPreference = 'Stop'
function Move-Item {
    param([string]$LiteralPath, [string]$Destination)
    Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination
    if ([IO.Path]::GetFileName($LiteralPath) -eq 'mika') { throw 'Injected interruption after directory swap.' }
}
& $Installer
''')
        failure = subprocess.run([str(x) for x in [*command[:-1], wrapper, source / 'install.ps1']],
                                 env={**env, 'MIKA_ARCHIVE_PATH': str(old)}, capture_output=True, timeout=60)
        assert failure.returncode != 0, failure.stdout
        assert (root / 'bin/mika.exe').read_bytes() == before
        assert not (root / 'previous-app').exists()
        # No-op must not read or download the archive, but still repair PATH.
        hidden = args.archive.with_name('hidden.zip')
        args.archive.rename(hidden)
        try:
            assert 'already up to date' in run(command, env=env)
        finally:
            hidden.rename(args.archive)
        obsolete = root / 'bin/obsolete-test'
        obsolete.write_text('remove on explicit repair')
        assert 'Reinstalled Mika' in run(command, env={**env, 'MIKA_REINSTALL': '1'})
        assert not obsolete.exists()
        assert marker.read_text() == 'keep model data'
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
            entries = winreg.QueryValueEx(registry, 'Path')[0].split(';')
        assert sum(x.rstrip('\\').lower() == str(root / 'bin').lower() for x in entries) == 1
    assert run([root / 'bin/mika.exe', '--version']).strip() == expected_version
    probe = root / 'bin/mika-inference-test.exe'
    shutil.copy2(args.stage / 'bin/mika-inference-test.exe', probe)
    assert 'ask not what your country' in run([probe, args.model, args.sample])
print('PASS: staged/relocated inference, dependencies, checksummed install, and startup')

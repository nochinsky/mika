"""CI validation of installed libraries and installers; never records microphone audio."""
import argparse
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--stage', type=Path, required=True)
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--model', type=Path, required=True)
parser.add_argument('--sample', type=Path, required=True)
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
    run(command, env=env)
    run(command, env=env)  # Reinstallation must work and preserve the data directory.
    assert run([root / 'bin/mika.exe', '--version']).strip() == expected_version
    probe = root / 'bin/mika-inference-test.exe'
    shutil.copy2(args.stage / 'bin/mika-inference-test.exe', probe)
    assert 'ask not what your country' in run([probe, args.model, args.sample])
print('PASS: staged/relocated inference, dependencies, checksummed install, and startup')

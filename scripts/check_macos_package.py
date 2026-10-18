"""Native macOS ARM64 CPU-only package/relocation checks; never opens a microphone."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
from evaluate_punctuation import events


def run(command, **kwargs):
    result = subprocess.run([str(value) for value in command], capture_output=True, text=True, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{command}\n{result.stdout}\n{result.stderr}')
    return result


def inference(probe, model, sample):
    raw = run([probe, model, sample, '--raw']).stdout
    formatted = run([probe, model, sample])
    assert 'ask not what your country can do for you' in raw, raw
    assert 'formatting=0 ' in formatted.stderr, formatted.stderr
    events(raw, formatted.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'stage', 'archive', 'model', 'sample'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('Run this validation on a native Apple Silicon Mac')
    cache = dict(line.split('=', 1) for line in (args.build / 'CMakeCache.txt').read_text().splitlines()
                 if '=' in line and not line.startswith(('#', '//')))
    for flag in ('TRANSCRIBE_METAL', 'TRANSCRIBE_VULKAN', 'TRANSCRIBE_CUDA', 'TRANSCRIBE_HIP',
                 'GGML_METAL', 'GGML_VULKAN', 'GGML_CUDA', 'GGML_HIP', 'GGML_SYCL',
                 'GGML_OPENCL', 'GGML_WEBGPU', 'GGML_RPC', 'GGML_CPU_ALL_VARIANTS',
                 'TRANSCRIBE_GGML_BACKEND_DL', 'TRANSCRIBE_BUILD_SHARED'):
        assert cache.get(flag + ':BOOL') == 'OFF', (flag, cache.get(flag + ':BOOL'))
    binaries = [args.stage / 'bin/mika', *sorted((args.stage / 'bin/punctuation').glob('*.dylib'))]
    assert len(binaries) == 3, binaries
    for binary in binaries:
        assert run(['lipo', '-archs', binary]).stdout.strip() == 'arm64'
        run(['codesign', '--verify', '--strict', binary])
        for line in run(['otool', '-L', binary]).stdout.splitlines()[1:]:
            dependency = line.strip().split(' (', 1)[0]
            assert dependency.startswith(('/usr/lib/', '/System/Library/', '@rpath/', '@loader_path/')), dependency
        # A default ORT session uses CPU; the upstream runtime can contain unused
        # Core ML support. Do not confuse an available provider with selection.
        if binary.name == 'mika':
            dependencies = run(['otool', '-L', binary]).stdout
            assert '/Metal.framework/' not in dependencies and '/CoreML.framework/' not in dependencies
    inference(args.stage / 'bin/mika-inference-test', args.model.resolve(), args.sample.resolve())
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='Mika relocated Mac ü ') as directory:
        home = Path(directory)
        env = {**os.environ, 'HOME': str(home), 'ZDOTDIR': str(home), 'XDG_CONFIG_HOME': str(home / '.config'),
               'SHELL': '/bin/zsh', 'MIKA_ARCHIVE_PATH': str(args.archive.resolve()),
               'MIKA_KEEP_MODEL': '0', 'MIKA_UNINSTALL_YES': '1'}
        run(['/bin/bash', source / 'install-macos.sh'], env=env)
        app = home / 'Library/Application Support/Mika/app'
        assert run([home / '.local/bin/mika', '--version']).stdout.startswith('mika ')
        shutil.copy2(args.stage / 'bin/mika-inference-test', app / 'bin/mika-inference-test')
        inference(app / 'bin/mika-inference-test', args.model.resolve(), args.sample.resolve())
        run(['/bin/bash', source / 'install-macos.sh'], env=env)
        model_dir = app.parent / 'models'
        model_dir.mkdir()
        (model_dir / 'granite-speech-5.0-470m-turboctc-Q4_K_M.gguf').write_bytes(b'removal fixture, not inference input')
        run(['/bin/bash', source / 'uninstall-macos.sh'], env=env)
        assert not app.parent.exists()
        assert not (home / '.local/bin/mika').is_symlink()
    print('PASS: native ARM64 CPU flags, ad-hoc signatures, system-only dependencies, staged/installed/relocated raw/default inference and removal. No microphone tested.')


if __name__ == '__main__':
    main()

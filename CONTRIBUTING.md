# Building and contributing

Read [GOAL.md](GOAL.md) first. Mika is a one-shot English dictation CLI, not a
configurable speech platform. Keep changes small and preserve stdout/exit behavior.

## Build requirements

- x86-64 Linux or Windows; experimental macOS 14+ ARM64. CMake **3.24+**,
  C17/C++17 compiler and threads. See [macOS build/status](docs/macos.md).
- libcurl **7.85+**, OpenSSL Crypto **1.1.1+** (or the pinned vcpkg manifest).
- **Python 3.12+ and the pinned conversion requirements for development/builds**.
  Python is never an installed-app dependency.

Model preparation is intentionally unchanged: CMake fetches pinned original
FullStop weights, reproduces and verifies INT8 conversion, and prepares a sibling
`bin/punctuation/` payload. First builds download the 210 MB original weights,
CPU ONNX Runtime assets and SentencePiece/transcribe.cpp/miniaudio sources.
Verified downloads are cached under the build directory. No conversion occurs in
normal app use. Exact provenance/versions are in [docs/punctuation.md](docs/punctuation.md).

Create a local tooling environment (use an installed Python 3.12+ interpreter):

```sh
python3 -m venv build-tools
build-tools/bin/python -m pip install -r scripts/requirements-punctuation.txt
```

On Windows use `py -3.12 -m venv build-tools`, then
`build-tools\Scripts\python.exe -m pip install -r scripts/requirements-punctuation.txt`.
Activation and a global execution-policy change are unnecessary.

### Linux

Install compiler/CMake/curl/OpenSSL development dependencies using your OS tools.
On recent Ubuntu/Debian: `build-essential cmake pkg-config libcurl4-openssl-dev
libssl-dev`; Arch: `base-devel cmake curl openssl`. Ensure the versions above are
met. ALSA/PulseAudio runtime libraries load dynamically; no audio development
headers are needed.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DMIKA_NATIVE_CPU=ON \
  -DPython3_EXECUTABLE="$PWD/build-tools/bin/python"
cmake --build build --parallel 8
./build/bin/mika
```

`MIKA_NATIVE_CPU=ON` tunes the speech backend to this machine: **do not distribute
that binary to unrelated CPUs**. Default OFF is conservative; portable release
bundles use runtime CPU dispatch instead. Everything is CPU-only.

### Windows

Use Visual Studio 2022's Desktop development with C++ toolchain and vcpkg. From a
developer PowerShell, adjusting the vcpkg path:

```powershell
cmake -S . -B build -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DVCPKG_TARGET_TRIPLET=x64-windows-static -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded `
  "-DPython3_EXECUTABLE=$PWD/build-tools/Scripts/python.exe"
cmake --build build --config Release --parallel 8
.\build\bin\Release\mika.exe
```

There is one app configuration: formatting by default, `--raw` at runtime. There
is no experimental formatting switch or alternate model selector. Experimental
macOS support is ARM64-only, with one static CPU speech backend and no GPU/Core ML
execution; see [the native CI and hardware-testing limitations](docs/macos.md).
Keep the `punctuation/` directory beside the executable.

## Tests and measurements

For quick checks without model downloads/conversion or Python ML packages, use
[the separate model-free test entry point](docs/validation.md#fast-model-free-checks).
The same guide covers laptop duration/resource measurements, real microphone
startup timing, and an explicitly consented human spoken-prompt evaluation workflow.
See the [Core Ultra 5 laptop validation snapshot](docs/laptop-validation.md) for
measured results and the remaining natural-speech evidence gap.

```sh
ctest --test-dir build --output-on-failure
```

Tests use fake microphone/inference devices, synthetic PCM, isolated installer
homes, local HTTPS, authored prompts and native formatting. They do not record a
microphone. Build-time asset preparation uses the network; tests themselves do not.
The `openssl` executable is needed to generate test TLS certificates.

To enable public-file speech tests using an existing verified Granite model:

```sh
cmake -S . -B build -DMIKA_TEST_MODEL=/absolute/path/to/model.gguf
cmake --build build --parallel 8
ctest --test-dir build --output-on-failure
./build/bin/mika-audio-devices  # metadata only, never records
```

Real-model tests run raw and default-formatted public JFK audio, including a
300-second repetition/length regression. That is not natural dictation accuracy.
`MIKA_SANITIZERS=ON` in a separate build instruments owned code on GCC/Clang; use
`ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`. Third-party libraries
are not themselves instrumented. Never replace missing hardware testing with a
claim that console fixtures prove every desktop microphone works.

The scripts `evaluate_punctuation.py`, `benchmark_punctuation.py`, and
`benchmark_pipeline.py` record style metrics, full formatting-stage cost and
public-file pipeline cost. The pipeline probe includes the Granite checksum and
reports model-ready timing, but does not measure actual microphone opening or
end-to-end time to Listening. Resource scopes belong beside every published number.
The old prose-style thresholds remain advisory; never change references just to
turn a score green. Prompt fixtures test post-formatting preservation, not whether
ASR heard the intended words.

## Installation and releases

`cmake --install build --prefix "$HOME/.local"` installs a source build and its
formatting payload/docs/licenses; multi-config generators need `--config Release`.
This is not an installer-managed app. Move a regular `~/.local/bin/mika` aside
before switching to the release installer's symlink.

For portable releases follow [.github/workflows/build.yml](.github/workflows/build.yml):
Ubuntu 22.04/glibc 2.35 and native Windows Server 2022, pinned static curl/crypto,
CPU-dispatched speech modules, and the existing formatter payload. A system-library
source build is **not** a standalone release just because dispatch is enabled.
CI validates default/raw inference after real installation/relocation, console and
installer transactions, integrity/fallback/cancellation, and public five-minute
processing before a matching tag may publish. No private audio or test executables
are packaged. Formatting weights are included; the speech GGUF is not.

For a dependency/model update: pin source and artifact identities, preserve notices
and modification provenance, reproduce the conversion hash, run metadata/safety
checks and both native jobs, and inspect quality/resource changes. Update security
sensitive dependencies deliberately; do not automatically chase new speech models.

For a release: update the CMake project version and `vcpkg.json` together, update
release notes/docs, validate both native jobs, then push the matching `vX.Y.Z` tag.
The generated version header also supplies the downloader user-agent. Do not rewrite
published tags. Keep original Mika MIT code separate from model/dependency licenses.

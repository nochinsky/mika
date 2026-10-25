# Contributing

Mika is a one-shot English dictation CLI. Read [the scope](GOAL.md) and
[architecture](docs/architecture.md) before changing runtime behavior. Keep changes
focused and preserve the transcript, cancellation, privacy and exit-code contracts.

## Build requirements

- **Mac:** Apple Silicon ARM64, macOS 14+, Xcode Command Line Tools; experimental.
- **Linux:** x86-64, C17/C++17 compiler and native development dependencies.
- **Windows:** x64, Visual Studio 2022 Desktop development with C++ and vcpkg.
- **All platforms:** CMake 3.24+, libcurl 7.85+, OpenSSL Crypto 1.1.1+, Python 3.12+
  and the pinned build-only conversion requirements.

Python is a development dependency, not an installed-app requirement. Initial
builds fetch pinned native sources, FullStop weights, CPU ONNX Runtime and the
Silero VAD. FullStop INT8 conversion is reproduced and verified; prepared data is
cached in the build directory. Model and dependency identities are pinned in
source; see [notices](THIRD_PARTY_NOTICES.md) and [formatting provenance](docs/punctuation.md#provenance-and-licenses).

Create a project-local tooling environment:

```sh
python3 -m venv build-tools
build-tools/bin/python -m pip install -r scripts/requirements-punctuation.txt
```

On Windows, use `py -3.12 -m venv build-tools` and
`build-tools\Scripts\python.exe -m pip install -r scripts/requirements-punctuation.txt`.
Activation or a global PowerShell execution-policy change is unnecessary.

### Mac

Homebrew may supply **developer-only** CMake, curl and OpenSSL dependencies:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=14.0 -DMIKA_NATIVE_CPU=OFF \
  -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3)" \
  -DCURL_ROOT="$(brew --prefix curl)" \
  -DPython3_EXECUTABLE="$PWD/build-tools/bin/python"
cmake --build build --parallel 4
./build/bin/mika
```

Mac uses one static CPU speech backend. See [Mac security and acceptance status](docs/macos.md).

### Linux

Install compiler, CMake, pkg-config, curl and OpenSSL development packages through
your package manager. ALSA/PulseAudio runtime libraries load dynamically; audio
headers are not required.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DPython3_EXECUTABLE="$PWD/build-tools/bin/python"
cmake --build build --parallel 4
./build/bin/mika
```

### Windows

From a developer PowerShell, adjust the vcpkg path:

```powershell
cmake -S . -B build -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DVCPKG_TARGET_TRIPLET=x64-windows-static -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded `
  "-DPython3_EXECUTABLE=$PWD/build-tools/Scripts/python.exe"
cmake --build build --config Release --parallel 4
.\build\bin\Release\mika.exe
```

Keep `punctuation/` and `speech/` beside the executable. `--raw` skips formatting,
not verified speech admission. `MIKA_NATIVE_CPU=ON` optionally tunes a local speech
build to its host; do not distribute it to unrelated CPUs. A system-library build
is not a portable release bundle.

## Test and measure

```sh
ctest --test-dir build --output-on-failure
```

Multi-config Windows builds need `-C Release`. Tests use fake capture, synthetic
PCM, public audio, isolated installer homes and local HTTPS—not live microphones.
The `openssl` executable generates local test certificates. Build-time preparation
uses the network; the test suite does not.

For checks without model downloads, ONNX Runtime or Python ML packages, use the
[model-free build](docs/validation.md#fast-model-free-checks). Configure a separate
build with `MIKA_SANITIZERS=ON` to instrument Mika-owned code on GCC/Clang; run with
`ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`.

Enable public-file recognition and five-minute tests with an existing verified model:

```sh
cmake -S . -B build -DMIKA_TEST_MODEL=/absolute/path/to/model.gguf
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

[Validation tools](docs/validation.md) cover file latency/memory, opt-in microphone
timing and separately consented private recordings. Keep private data out of Git,
CI and release assets. Public-file accuracy and fake-device results do not replace
hardware testing. Preserve references and report failures; do not adjust scoring
or invent literal corrections to improve results.

## Install and release

`cmake --install build --prefix "$HOME/.local"` installs a source build, not an
installer-managed application. Move an existing regular `~/.local/bin/mika` aside
before switching to a release installer's symlink.

Portable builds follow [the workflow](.github/workflows/build.yml): native Mac
ARM64, Linux x86-64/glibc 2.35 and Windows x64, pinned static curl/crypto and the
bundled formatting/VAD data. The separately cached Granite model is not packaged.

For a release:

1. Update `CMakeLists.txt`, `vcpkg.json`, release notes and relevant documentation.
2. Validate all three native jobs, model-free tests and installer/removal checks.
3. Push the matching immutable `vX.Y.Z` tag. Never rewrite published tags.
4. The publisher requires three archives and three checksums, validates embedded
   versions/hashes, uploads to a draft and makes it public/latest only after all
   six assets are uploaded.

Maintainers can also use **Actions → Build and test → Run workflow**, select
`main`, and enable **publish_release**. The same native jobs and release gates
run before the publisher creates the source version's tag at the tested commit
and publishes all six assets. The option defaults to false; ordinary manual
runs remain validation-only. Existing tags must already point to that exact
commit and are never moved. No local Git credentials are required for this route.

Mac remains experimental pending [hardware acceptance](docs/macos.md#validation-status).
Ad-hoc CI signing is not Developer ID signing or notarization. Dependency/model
updates must pin identities, preserve licenses and modification notices, reproduce
conversion hashes and review quality/resource changes on all platforms.

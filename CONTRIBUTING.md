# Building and contributing

Mika is C17, with C++17 inference internals accessed through a C API. There is no
Python runtime dependency. CMake fetches hash-pinned transcribe.cpp and miniaudio
sources once and caches them under `build/_deps`.

## Build locally

Requires CMake **3.24+**, a C17/C++17 compiler, libcurl **7.85+**, OpenSSL/libcrypto
**1.1.1+**, and threads. Ordinary source builds use system libraries; these are not
standalone distribution packages.

### Linux

On a recent Ubuntu/Debian system with the required dependency versions:

```sh
sudo apt-get install --no-install-recommends \
  build-essential cmake pkg-config libcurl4-openssl-dev libssl-dev
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DMIKA_NATIVE_CPU=ON
cmake --build build --parallel 8
./build/bin/mika
```

Arch equivalents: `base-devel cmake curl openssl`. System ALSA or PulseAudio runtime
libraries are loaded dynamically; audio development headers are not required.

`MIKA_NATIVE_CPU=ON` tunes to your CPU. **Do not distribute this binary to unrelated
CPUs.** Default `OFF` is a conservative baseline; release bundles use runtime CPU
dispatch instead. All modes are CPU-only, with no GPU driver required.

### Windows

Use Visual Studio 2022's Desktop development with C++ toolchain and
[vcpkg](https://github.com/microsoft/vcpkg). From a developer PowerShell, adjusting
its toolchain path:

```powershell
cmake -S . -B build -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DVCPKG_TARGET_TRIPLET=x64-windows-static -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded
cmake --build build --config Release --parallel 8
.\build\bin\Release\mika.exe
```

The root manifest pins curl/crypto dependencies. Native CI validates Windows builds,
installed inference, installer transactions, and classic-console UI using fake audio.
The initial release was also user-tested with a real Windows microphone and Enter.
Permissions and audio hardware still vary between desktops.

### macOS — source-only, unvalidated

```sh
xcode-select --install
brew install cmake pkg-config curl openssl@3
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DMIKA_NATIVE_CPU=ON \
  -DCMAKE_PREFIX_PATH="$(brew --prefix curl);$(brew --prefix openssl@3)"
cmake --build build --parallel 8
./build/bin/mika
```

Allow microphone access for your terminal. Model storage uses
`~/Library/Application Support/Mika/models`. There is no prebuilt macOS release.

### Optional source installation

```sh
cmake --install build --prefix "$HOME/.local"
```

Ensure `~/.local/bin` is on PATH; multi-configuration generators also require
`--config Release`. This installs docs/licenses as well as the executable. A source
installation into `~/.local/bin/mika` is not managed by the release installer; move
that regular executable aside before switching to the installer-managed symlink.

## Tests

```sh
ctest --test-dir build --output-on-failure
```

Default tests use synthetic PCM, fake audio/inference, isolated installer homes,
and a local HTTPS server. They never record a microphone or download a model.
Python 3.8+ is needed for richer tests; the `openssl` executable generates local
TLS certificates. Missing optional test prerequisites are reported as skips.

Coverage includes model integrity, bounded PCM, HTTPS and redirect failures,
cancellation, terminal restoration, transient status erasure/narrow consoles,
redirected output, update/no-op/repair, rollback, concurrency and model retention.
POSIX controls use PTYs; Windows controls use a private classic console. Neither
substitutes for a live hardware test on each desktop platform.

Opt into the public JFK sample using an already cached model:

```sh
cmake -S . -B build -DMIKA_TEST_MODEL=/absolute/path/to/model.gguf
cmake --build build --parallel 8
ctest --test-dir build --output-on-failure
./build/bin/mika-inference-test /path/to/model.gguf /path/to/sample.wav
./build/bin/mika-audio-devices  # metadata only; never records
```

With Python and `MIKA_TEST_MODEL`, CTest runs both the short sample and
`real-model-long`: a generated 300-second input repeating the public speech in
25 slots. The long test checks that all slots and the final phrase are represented;
it is not a five-minute dictation accuracy benchmark. It can use substantially
more memory and time than the short test, especially on baseline CPUs.

`MIKA_SANITIZERS=ON` instruments owned code with ASan/UBSan on GCC/Clang. Use a
separate build directory and `ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`.
Third-party internals are not instrumented by this option.

## Releases

Update the CMake project version and manifest version together, then validate CI
and push the matching `vX.Y.Z` tag. Do not replace an already published tag.
The workflow publishes only after both platform jobs succeed.

Linux builds use Ubuntu 22.04 (glibc 2.35 baseline); Windows builds run natively on
Windows Server 2022 with a static CRT. Curl/crypto are statically linked using the
pinned vcpkg baseline; Windows HTTPS uses native Schannel. Runtime-dispatched
inference modules ship next to Mika with relative lookup paths.

CI downloads the fixed model through Mika's real downloader, transcribes the public
JFK sample plus its five-minute length regression, installs/relocates the package
and checks installer failure paths.
`scripts/package.py` ships only application binaries/libraries and documentation,
including all required notices. Model weights, build directories and private audio
are never release assets. See `.github/workflows/build.yml` for exact commands.

Keep the normal CLI small: no account, wizard, background daemon, automatic update
check during dictation, or unnecessary stdout output. Preserve the distinction
between Mika's [MIT license](LICENSE) and [third-party licenses](THIRD_PARTY_NOTICES.md).

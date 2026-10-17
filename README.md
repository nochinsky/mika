# Mika

A small, one-shot, offline **English speech-to-text CLI**. Speak into the default
microphone, press **Enter**, and get the transcript in your terminal.

- **Enter:** finish recording and transcribe.
- **Esc / Ctrl+C:** cancel without printing a transcript.
- **60 seconds:** recording automatically stops and transcribes at this limit.
- Audio stays in memory and is discarded after the command; no audio files,
  transcript history, clipboard integration, background service, or setup wizard.
- Only the transcript goes to **stdout**; all status messages go to **stderr**.

```sh
mika
mika > notes.txt
mika --help
mika --version
```

Wait for **Listening** before speaking. Select your default microphone in your
operating system's sound settings. The stopping keys apply to Mika's focused
terminal, not globally to other applications.

## Install — Linux, Arch, WSL, and Windows

Prebuilt **x86-64** releases need no compiler, Python, GPU, or administrator access.
The installers verify the release archive's SHA-256, test the binary before
publishing it, and install only for your user. No microphone is opened and no model
is downloaded by the installer.

### Linux / Arch Linux / WSL

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

Then restart your terminal (or run the printed PATH command) and type `mika`.
Linux packages require **glibc 2.35+**: current Arch Linux and Ubuntu/WSL 22.04+
are targets. Alpine/musl, 32-bit CPUs, and ARM are not covered by these binaries.
You still need an OS audio input/backend. A normal Arch PipeWire desktop should
have `libpulse` and the PipeWire PulseAudio compatibility service; the installer
never replaces your audio stack or runs pacman/apt automatically.

### Windows — PowerShell

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

Run in **Windows PowerShell 5.1+ or PowerShell 7**, as your normal user. Then type
`mika`; restart the terminal for PATH changes to apply to future sessions. Targets
are **Windows 10/11 x64**. WSL uses the Linux command above, not this script.

Prefer to inspect a script before executing it? Download it first, review it, and
run `bash install.sh` or `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1`.
No machine-wide execution-policy change is made. Checksums protect against
corrupt downloads; the installer and release assets are trusted from this GitHub
repository, not independently signed artifacts.

### Updates, paths, and removal

Rerun the same installer to update. The model cache is preserved. Close running
Mika processes before updating on Windows. Set `MIKA_VERSION=v0.1.0` to pin a
release instead of `latest`.

| Platform | Application | Command / PATH entry |
| --- | --- | --- |
| Linux/WSL | `${XDG_DATA_HOME:-~/.local/share}/mika/app` | `~/.local/bin/mika` symlink |
| Windows | `%LOCALAPPDATA%\\Mika\\app` | `%LOCALAPPDATA%\\Mika\\app\\bin` |

To remove Mika, delete that application's `app` directory and the Linux symlink
or Windows user-PATH entry. Model files are separate, so remove `models` as well
only if you want to reclaim the model download. Linux shell profiles contain a
marked Mika PATH block; it may be removed, but `~/.local/bin` is commonly useful
for other applications too.

Manual/offline packages are on [GitHub Releases](https://github.com/nochinsky/mika/releases).
Download the platform archive **and its `.sha256` sidecar**. An optional
`MIKA_ARCHIVE_PATH` environment variable lets either installer use those local
files instead of downloading them. The SHA-256 sidecar must be beside the archive.

The first **run of `mika`**, not installation, asks before downloading the fixed
279 MB model. After that, speech recognition works offline.

## Build from source

Application code is C17. Inference uses the C API of `transcribe.cpp`, whose
implementation requires a C++17 compiler. There is **no Python runtime dependency**.
CMake downloads hash-pinned inference/audio sources on the first configure; those
sources are cached under `build/_deps`. You need an internet connection for this
first build, but not for subsequent builds using that cache.

### Linux (Ubuntu / Debian)

```sh
sudo apt-get install --no-install-recommends \
  build-essential cmake pkg-config libcurl4-openssl-dev libssl-dev

# Recommended when building for your own machine:
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DMIKA_NATIVE_CPU=ON
cmake --build build --parallel 8
./build/bin/mika
```

Requires CMake **3.24+**, libcurl **7.85+**, and OpenSSL **1.1.1+** (libcrypto for
SHA-256). The audio library dynamically loads system audio backends; ALSA or
PulseAudio runtime libraries are needed, not their development headers. PipeWire
setups can use their PulseAudio compatibility service.

**Binary portability:** `MIKA_NATIVE_CPU=ON` enables this machine's CPU instruction
set and is much faster on suitable CPUs. Do **not** distribute that binary to
unrelated CPUs. The default is `OFF`, a conservative baseline build. Use a fresh
build directory for a release/portable build:

```sh
cmake -S . -B build-portable -DCMAKE_BUILD_TYPE=Release -DMIKA_NATIVE_CPU=OFF
cmake --build build-portable --parallel 8
```

Both modes use CPU inference only. No CUDA, Vulkan, Metal, or GPU driver is needed.
Thread count uses the inference library's automatic default.

### macOS (source build; native validation still required)

Install Xcode Command Line Tools and the dependencies with Homebrew:

```sh
xcode-select --install
brew install cmake pkg-config curl openssl@3
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DMIKA_NATIVE_CPU=ON \
  -DCMAKE_PREFIX_PATH="$(brew --prefix curl);$(brew --prefix openssl@3)"
cmake --build build --parallel 8
./build/bin/mika
```

Allow microphone access for your terminal/application when macOS requests it.

### Windows (source build)

Use Visual Studio 2022's **Desktop development with C++** toolchain, CMake, and
[vcpkg](https://github.com/microsoft/vcpkg). From a developer PowerShell:

```powershell
vcpkg install curl:x64-windows openssl:x64-windows
cmake -S . -B build -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DVCPKG_TARGET_TRIPLET=x64-windows
cmake --build build --config Release --parallel 8
.\build\bin\Release\mika.exe
```

Adjust the vcpkg path. Keep vcpkg's copied runtime DLLs beside the executable.
Windows paths are handled as UTF-8 at the application boundary and converted to
Unicode filesystem/console APIs. Native CI validates Windows builds, installers,
and packaged inference; microphone permissions and interactive keyboard controls
still need a smoke test on your actual Windows desktop.

### Optional installation

```sh
cmake --install build --prefix "$HOME/.local"
# Ensure ~/.local/bin is on PATH, then run:
mika
```

For a multi-configuration generator, also pass `--config Release`. The binary,
documentation, and third-party notices are installed. For ordinary source builds, system libcurl, libcrypto,
and C++ runtime dependencies still need to be available. The one-line installers
use separate self-contained release bundles instead.

## First launch and model storage

The first launch asks permission before downloading **279,114,080 bytes** (about
279 MB) from Hugging Face. Press **y** to approve; any other key declines. There is
no `mika setup`. The model is fixed to the standard Apache-2.0 variant, **not** the
non-commercial `-nc` variant:

```text
granite-speech-5.0-470m-turboctc-Q4_K_M.gguf
```

| Platform | Model directory |
| --- | --- |
| Linux | `$XDG_DATA_HOME/mika/models`, or `~/.local/share/mika/models` |
| macOS | `~/Library/Application Support/Mika/models` |
| Windows | Local AppData known folder + `Mika/models` |

Relative/empty `XDG_DATA_HOME` values fall back to the home directory. No settings
file is created. An empty `.download.lock` file may remain in the model directory
for concurrent-install protection; it is not a background process.

Model identity is pinned in [`src/model.h`](src/model.h):

```text
Repository: handy-computer/granite-speech-5.0-470m-turboctc-gguf
Revision:   0cf5be9f4bcd479989e6a24d142094d34d552daa
SHA-256:    3f30525381d72246b7f99e49b6cb66b249cf1b990c6c3d0e031a7765735f513e
```

Mika checks the exact byte count and SHA-256 on **every launch**. Downloads require
HTTPS and certificate verification, have redirect/connect/stall/time limits, and
write to a private temporary file in the same directory. Only a complete verified
file replaces the destination. Failed/cancelled transfers are discarded and are
not resumed; an interrupted process killed forcibly can leave a `.part.*` file,
which can be removed when no download is running. A corrupt model triggers the
same consented download flow, rather than being silently trusted or overwritten.

After installation, transcription is offline: audio is not uploaded. Model
updates are deliberate source changes, not silent downloads of a moving version.
For private corporate CA certificates, `CURL_CA_BUNDLE` can name a trusted PEM
bundle; this does not disable certificate verification or the pinned checksum.

## Tests

The default tests do **not** record audio or download models. They use synthetic
PCM, a fake microphone/inference fixture for terminal controls, and a local HTTPS
server for the **real** downloader. Python 3.8+ runs the CLI/network tests, and the
`openssl` command generates a short-lived local test certificate. Without Python,
CMake registers only the C unit tests; without the `openssl` executable, the local
HTTPS suite reports a skip.

```sh
ctest --test-dir build --output-on-failure
```

Covered: checksum vectors, truncated/corrupt/oversized downloads, redirect policy,
TLS trust, cancellation, atomic replacement, private temporary files, concurrent
locks, PCM capacity bounds, help/arguments, stdout failures, first-run refusal,
terminal restoration, Enter/Esc/Ctrl+C, microphone/inference failures, and the
recording duration limit. POSIX PTY tests are skipped on Windows; its console
requires a native test.

Opt into real-model inference using an already installed model:

```sh
cmake -S . -B build \
  -DMIKA_TEST_MODEL="$HOME/.local/share/mika/models/granite-speech-5.0-470m-turboctc-Q4_K_M.gguf"
cmake --build build --parallel 8
ctest --test-dir build --output-on-failure
```

This adds the public JFK sample test. The sample is supplied by the pinned backend
source archive; no microphone is used. For a direct inference probe:

```sh
./build/bin/mika-inference-test /path/to/model.gguf /path/to/sample.wav
./build/bin/mika-audio-devices  # input metadata only; never opens a recording stream
```

`MIKA_SANITIZERS=ON` instruments Mika-owned code with AddressSanitizer and UBSan on
GCC/Clang. For example, configure a separate `build-asan` directory, build, and run
CTest with `ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`. Dependency
internals are not instrumented by this option.

## Current limitations

- English only; no live partial transcript, timestamps, translation, or diarization.
- Short, single-speaker dictation, capped at 60 seconds to bound memory. The model
  is loaded for each invocation; long-form recording/chunking is outside v1.
- This raw CTC model may emit lowercase, unpunctuated text. Mika prints its output
  without adding an LLM or promising polished punctuation.
- A controlling terminal is required even when stdout is redirected. SSH needs an
  interactive terminal **and an audio input available on the remote machine**;
  Mika does not forward a client microphone.
- Cancellation during synchronous model loading or an encoder pass can take until
  that operation returns. Cancelled work never emits a partial transcript.
- Actual microphone capture, permissions, and native keyboard controls need manual
  smoke tests on your hardware. Native release CI checks builds, file safety,
  packaged inference, and installers without recording private audio. macOS is
  still source-only and has not been validated here.

Exit codes: **0** success/help/version, **1** failure, **2** invalid arguments,
**130** cancellation (including declining a download).

## Release builds

GitHub Actions builds Linux packages on Ubuntu 22.04 and Windows packages natively
on Windows Server 2022. Curl/crypto dependencies are statically linked from the
pinned `vcpkg.json`; Windows uses a static CRT, so no Visual C++ installer is needed.
Inference ships a baseline CPU module plus optimized modules selected at runtime
for the host CPU, rather than assuming the release builder's CPU matches yours.
All packaged libraries are installed beside Mika with relative lookup paths.

CI runs the offline test suite, downloads the pinned model through the real C
downloader, transcribes the public JFK sample, and validates real installation and
inference after relocation. Only platform archives and checksums are uploaded;
model weights, build directories, and private audio are not published. Pushing a
version tag publishes a release only after both platform jobs pass. `scripts/package.py`
includes the MIT license and dependency/model notices in each archive.

Mika's original code is [MIT-licensed](LICENSE). See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for model and dependency
attribution and the included license texts.

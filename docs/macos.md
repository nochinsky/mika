# Experimental macOS support

Target: **Apple Silicon ARM64, macOS 14+**, native terminal. Intel Macs, Rosetta
execution, universal binaries, Metal/GPU inference and Core ML execution are not
supported. This is the same one-shot CLI and fixed models as Linux/Windows.

Speech uses one statically linked native **CPU** backend. Metal, Vulkan, CUDA,
HIP, SYCL, OpenCL, WebGPU and RPC backends are disabled. The native formatter uses
a default ONNX Runtime session with only the built-in CPU provider selected;
Mika never appends Core ML or another accelerator. The pinned upstream Mac runtime
contains unused Core ML provider support and links that system framework; that
is not a request to run inference on it. Apple's Accelerate CPU BLAS is used by
the pinned speech decoder; it is not a Metal/Core ML inference backend.

## Install and update

**v0.3.0 and later include a public Mac download** alongside Linux and Windows:
[`mika-macos-arm64.tar.gz` and its checksum](https://github.com/nochinsky/mika/releases/latest).
Mac support remains **experimental**, not hardware-certified stable support.
Native hosted ARM64 tests pass, but the physical-device checklist below is pending.

Install, or rerun to update, as your normal user without root, Homebrew, Python or
a compiler:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | bash
```

Restart your terminal if `mika` is not found, then run `mika --version` and `mika`.
Speak after Listening; Enter finishes, Esc/Ctrl+C cancels. The terminal may need
microphone permission; see the limitations below.

For an explicit version instead of latest:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | MIKA_VERSION=v0.3.0 bash
```

For manual/offline app installation, download both archive and adjacent `.sha256`
from the same release and save its `install-macos.sh` source, then run:

```sh
MIKA_ARCHIVE_PATH="$HOME/Downloads/mika-macos-arm64.tar.gz" bash install-macos.sh
```

The first Granite model download is separate and requires network/consent; a fully
offline dictation machine must already have that verified model. `MIKA_VERSION`,
`MIKA_REINSTALL=1` and `MIKA_ARCHIVE_PATH` work like the Linux and Windows installers. Downloads use HTTPS, limits and SHA-256. Archives may contain
only regular files/directories under `mika/`; symlinks and special files are
rejected. A failed directory swap restores the previous app. The speech model
is consented separately on first run and is kept across app updates.

The installer places the app at `~/Library/Application Support/Mika/app`, speech
weights at the sibling `models/`, and the command at `~/.local/bin/mika`. It adds
a marked PATH block to Zsh/Bash or the existing Fish-style configuration. Restart
your terminal. XDG data paths are not used for the Mac model directory.

Removal (one confirmation, removes the managed app and fixed cached model):

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | bash
```

To remove the app but keep the downloaded Granite model:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | MIKA_KEEP_MODEL=1 bash
```

To repair damaged app data, close Mika and rerun the installer with
`MIKA_REINSTALL=1`.

`--keep-model` / `MIKA_KEEP_MODEL=1` preserves weights; `--yes` /
`MIKA_UNINSTALL_YES=1` deliberately skips confirmation. Notes outside the app,
customized/linked shell profiles, unrelated commands/data and recovery directories
are preserved. Move personal files out of the managed app directory before removal.
The scripts use stock Bash 3.2/BSD utilities and an atomic `.maintenance-lock`
directory, not GNU flock. Close Mika before updating/removing it; removal also
checks open executable/model/download-lock files. If a forcibly killed maintenance
process leaves that directory behind, verify no installer/uninstaller is running
before manually removing **only the empty lock directory** and retrying.

## Microphone and distribution limitations

The executable embeds a microphone usage description. macOS may attribute access
to your terminal application; check System Settings → Privacy & Security →
Microphone and the system's default input. Permission prompts, denial/recovery,
real capture and terminal application behavior need testing on a physical Mac.
An automated public-file/PTY result is **not** evidence that these work.

Release binaries are **ad-hoc signed**, not Developer ID-signed/notarized. SHA-256
checksums detect corruption, not a compromised publisher. Gatekeeper/trust and
permission behavior on downloaded artifacts remain part of real-Mac acceptance;
no script disables Gatekeeper, strips quarantine or changes OS security policy.
Do not label this stable support until those checks have been performed.

## Physical-Mac acceptance checklist — pending

No physical Mac was available for this review. Before calling support stable:

- [ ] On native Apple Silicon/macOS 14+, download the candidate artifact through
  the normal browser path, verify its checksum/signature, and observe trust/
  quarantine behavior **without** stripping quarantine or disabling Gatekeeper.
- [ ] Fresh per-user install from that exact artifact; verify command/PATH and
  first-run model consent (decline, then accept) without sudo or developer tools.
- [ ] In the intended terminal app, test microphone permission deny, recovery and
  allow. Check the actual default input and intelligible captured speech, not
  merely the device list or advancing sample counter.
- [ ] Dictate short natural prompts, pauses, quiet speech and intentional silence;
  finish with Enter and review meaning/negations/numbers. Measure live
  Enter-to-output separately from file inference.
- [ ] Cancel during recording/loading/inference; confirm exit 130, empty stdout
  and restored terminal. Test stdout redirection as well as the visible terminal.
- [ ] Update/reinstall, forced repair, removal with/without keeping Granite, and
  interrupted-operation recovery; verify unrelated files/profiles remain intact.

Record OS/terminal/input/artifact identity and actual results. Developer ID signing
and notarization are **not implemented**; decide the distribution policy explicitly
rather than treating an ad-hoc CI signature as equivalent acceptance.

## Building and automated evidence

Developer builds need Xcode Command Line Tools, CMake 3.24+, Python 3.12 with the
pinned conversion requirements, curl 7.85+ and OpenSSL Crypto 1.1.1+. Homebrew can
supply **developer-only** tools/libraries; installed Mika needs none of them.
For example, after creating the build-tools venv from CONTRIBUTING.md:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=14.0 -DMIKA_NATIVE_CPU=OFF \
  -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3)" \
  -DCURL_ROOT="$(brew --prefix curl)" \
  -DPython3_EXECUTABLE="$PWD/build-tools/bin/python"
cmake --build build --parallel 3
ctest --test-dir build --output-on-failure
```

The native `macos-14` CI lane uses pinned static vcpkg curl/crypto, verifies the
conversion hash, runs unit/PTY/local HTTPS/formatter tests plus real-file raw,
formatted and five-minute regressions, and tests scripts using system Bash/BSD
utilities. It checks ARM64 architecture, disabled GPU backend flags, signatures,
system-only dylib dependencies, installed/relocated inference and removal. The
Mac runtime archive is separately pinned in `scripts/fetch_punctuation.py`.
Local Linux script mocks are only logic tests, not proof of Darwin behavior.
The tag publication job waits for this Mac lane and both other platforms, then
requires all three archives/checksums with matching versions before making a
release public. Branch workflows also expose the `mika-macos-arm64` artifact for
development testing. No automated step records a microphone or packages test
executables/private audio.

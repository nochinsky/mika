## Mika — first desktop test release

Offline, English-only speech-to-text. Run `mika`, speak after **Listening**, press
**Enter** to transcribe, or **Esc / Ctrl+C** to cancel. Transcript output stays in
the terminal; no clipboard integration, setup wizard, or background daemon.

### Install

**Arch Linux / Linux / WSL (x86-64, glibc 2.35+):**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

**Windows 10/11 x64 — PowerShell:**

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

Install as your normal user, without sudo/admin. Linux may need a new terminal for
PATH activation; the installer also prints the direct command. Windows updates
its per-user PATH. Both installers verify archive checksums before installation.

The first **run** asks before downloading the fixed **279 MB Granite Speech 5.0
470M TurboCTC Q4_K_M** model. Later runs work offline. Release archives do not
include model weights. Audio stays in memory and is never uploaded or saved.

### Notes for testing

- Select your default microphone in OS sound settings. WSL requires a working
  WSLg/host audio input and Windows microphone permission.
- 60-second recording limit; at the limit, Mika transcribes automatically.
- Raw model output may be lowercase and unpunctuated.
- CPU optimized modules are selected at runtime; no GPU/compiler/Python needed.
- Linux and Windows CI validate real model inference, relocatable libraries,
  download integrity, and installation. Actual microphone/keyboard behavior still
  needs testing on your hardware; CI never records private audio.
- ARM, 32-bit systems, Alpine/musl, and prebuilt macOS packages are not included.

Report problems with OS/version, terminal, the command used, and exact error text.
Do not attach private recordings unless you deliberately choose to share them.

Mika code: MIT. Model: Apache-2.0. Dependency and model notices are bundled.

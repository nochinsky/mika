# Mika

Speak. Press **Enter**. Get text.

A small, offline English speech-to-text utility for your terminal.
No account, clipboard access, background service, or setup wizard.

## Install

**Linux / Arch / WSL**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

**Windows — PowerShell**

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

Install as your normal user—no sudo/admin, compiler, or Python needed.
Prebuilt releases support **x86-64 Linux (glibc 2.35+)** and **Windows 10/11 x64**.
Restart your terminal if `mika` is not found.

## Use

```sh
mika
```

Speak after **Listening**, then press **Enter** to finish. **Esc / Ctrl+C** cancels.
Mika uses your system's default microphone. Recordings automatically finish at
**5 minutes**. Press Enter sooner whenever you're done.

The first run asks before downloading the **279 MB** speech model. After that,
recognition works offline. Your audio stays in memory and is never uploaded or saved.

To save the transcript instead:

```sh
mika > notes.txt
```

## Update

Close Mika and rerun the same installation command. It installs the latest release,
or skips reinstallation if you're already current. Your downloaded model is kept.

[Help & advanced installation](docs/usage.md) · [Build & contribute](CONTRIBUTING.md) ·
[Releases](https://github.com/nochinsky/mika/releases)

[MIT](LICENSE) for Mika's code. [Model and dependency licenses](THIRD_PARTY_NOTICES.md).

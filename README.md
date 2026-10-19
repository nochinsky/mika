# Mika

Speak. Press **Enter**. Get text.

Fast, offline English dictation for AI-agent prompts and everyday terminal use.
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

**macOS:** an [experimental Apple Silicon CPU-only build](docs/macos.md) is available
through branch CI artifacts. It is not yet a stable release; Intel Macs are not supported.

## Use

```sh
mika
```

Speak after **Listening**, then press **Enter** to finish. **Esc / Ctrl+C** cancels.
Mika uses your system's default microphone. Recordings automatically finish at
**5 minutes**. Press Enter sooner whenever you're done.

Punctuation/capitalization is automatic. Use `mika --raw` to skip it. Formatting
never rewrites transcript words, but speech recognition and punctuation can still
be wrong—this is quick dictation, not an editor.

The first run asks before downloading the **279 MB** speech model. Formatting
assets come with the app. After that, everything works offline. Your audio stays
in memory and is never uploaded or saved.

To save the transcript instead:

```sh
mika > notes.txt
```

## Update

Close Mika and rerun the same installation command. It installs the latest release,
or skips reinstallation if you're already current. Your downloaded model is kept.

## Uninstall

Close Mika, then run as your normal user. Confirm to remove the app, downloaded
speech model, and installer-created command/PATH setup. Notes saved outside the
app directory are kept.

**Linux / Arch / WSL**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.sh | bash
```

**Windows — PowerShell**

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.ps1 | iex
```

[Removal details & keeping the model](docs/usage.md#uninstalling).

[Help & advanced installation](docs/usage.md) · [Build & contribute](CONTRIBUTING.md) ·
[Releases](https://github.com/nochinsky/mika/releases)

[MIT](LICENSE) for Mika's code. [Model and dependency licenses](THIRD_PARTY_NOTICES.md).

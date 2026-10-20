# Mika

Offline English dictation for **Mac, Linux and Windows**.
Run `mika`, speak, press **Enter**, and get text in your terminal.

No account, cloud processing, background service or clipboard access.

## Install

### Mac — experimental

Apple Silicon ARM64, macOS 14 or later. Intel Macs and Rosetta are not supported.

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | bash
```

Mac downloads are ad-hoc signed, **not notarized**. First use may require approval
in macOS Privacy & Security for the executable or formatter libraries.
Read the [Mac setup and security guide](docs/macos.md#first-run-security-approval).

### Linux

x86-64, glibc 2.35 or later.

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

### Windows

Windows 10 or 11, x64. Run in PowerShell:

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

Install as your normal user, without sudo or administrator access. No compiler,
Python or Homebrew is required. Restart your terminal if `mika` is not found.
[Manual downloads](https://github.com/nochinsky/mika/releases) are also available.

## Use

```sh
mika
```

Speak after **Listening**, then press **Enter** to finish. **Esc / Ctrl+C** cancels.
Mika uses your system's default microphone and limits each recording to five minutes.
Punctuation and capitalization are automatic; `mika --raw` skips formatting.

Only the transcript goes to stdout. To save it:

```sh
mika > notes.txt
```

The first run asks before downloading the **279 MB speech model**. Formatting and
speech-detection data are bundled. After setup, dictation works offline on the CPU.
Audio stays in memory and is never uploaded or saved by Mika.

Recognition and punctuation can be wrong. Review names, numbers, negations and
commands before using the text. Formatting does not correct misheard words.

## Update

Close Mika and rerun your platform's installation command. Your downloaded speech
model is kept. Check the installed version with `mika --version`.

## Uninstall

Close Mika and run the matching command. Confirm to remove the managed app,
downloaded model and Mika command/PATH setup. Files saved outside the app are kept.

**Mac**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | bash
```

**Linux**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.sh | bash
```

**Windows — PowerShell**

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.ps1 | iex
```

See [removal options](docs/usage.md#uninstalling) to keep the downloaded model.

## Documentation

- [Usage and troubleshooting](docs/usage.md) · [Mac support](docs/macos.md)
- [Build and contribute](CONTRIBUTING.md) · [Validation](docs/validation.md)
- [Architecture](docs/architecture.md) · [Formatting](docs/punctuation.md)

[MIT](LICENSE) for Mika's code. Models and dependencies have
[their own licenses](THIRD_PARTY_NOTICES.md).

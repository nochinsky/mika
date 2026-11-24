# Mika

Talk, press Enter, get text. Mika is a small dictation tool for the terminal that
runs entirely on your own machine, on **Mac, Linux and Windows**.

<p align="center">
  <img src="docs/demo.svg" alt="A terminal running mika: it shows Listening with a timer, then Transcribing, then prints the sentence that was spoken." width="680">
</p>

There's no account, no cloud, nothing running in the background, and it never
touches your clipboard. Your audio stays in memory and is thrown away when Mika exits.

It understands **English only** for now.

## Install

**Linux** (x86-64, glibc 2.35+)

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

**Windows** (10 or 11, x64), in PowerShell:

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

**Mac** (Apple Silicon, macOS 14+). Still experimental:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | bash
```

The Mac build isn't notarized, so macOS may ask you to approve it the first time.
The [Mac guide](docs/macos.md#first-run-security-approval) walks through it.
Intel Macs aren't supported.

You don't need admin rights, a compiler or Python. If `mika` isn't found afterwards,
open a new terminal. You can also grab builds from the
[releases page](https://github.com/nochinsky/mika/releases).

## Use it

```sh
mika
```

Wait for **Listening**, say what you want, and press **Enter**. Mika prints the
text and exits. **Esc** or **Ctrl+C** cancels.

Punctuation and capitals are added for you. If you'd rather have the words exactly
as recognized, use `mika --raw`.

The transcript is the only thing written to stdout, so you can send it anywhere:

```sh
mika > notes.txt
mika | wc -w
```

A few things to know:

- The first run asks before downloading the speech model (279 MB). After that,
  everything works offline on your CPU.
- Mika uses your system's default microphone. Change it in your OS sound settings.
- A recording can be up to five minutes long.
- It will sometimes mishear things. Check names, numbers and anything like "don't"
  vs "do" before you rely on the text, and especially before you run it as a command.

## Update

Run the install command again. It keeps the model you already downloaded.
`mika --version` shows what you have.

## Uninstall

Each script asks before removing anything. It removes the app, the downloaded
model and the `mika` command. Your own files are left alone.

```sh
# Linux
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.sh | bash

# Mac
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | bash
```

```powershell
# Windows
irm https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.ps1 | iex
```

To keep the model (say, because you plan to reinstall), see
[removal options](docs/usage.md#uninstalling).

## More

- [Usage and troubleshooting](docs/usage.md)
- [Mac support](docs/macos.md)
- [How it works](docs/architecture.md) and [how formatting works](docs/punctuation.md)
- [Building and contributing](CONTRIBUTING.md) and [validation](docs/validation.md)

Mika's code is [MIT](LICENSE). The models and libraries it uses have
[their own licenses](THIRD_PARTY_NOTICES.md).

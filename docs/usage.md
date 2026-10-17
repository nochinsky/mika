# Help and advanced installation

## Microphone and terminal

Choose the default input in your operating system's sound settings. Mika's terminal
must have focus for Enter/Esc/Ctrl+C. A controlling terminal is required even when
stdout is redirected. SSH does not forward a microphone automatically.

- **Arch / PipeWire:** have `libpulse` and your usual PulseAudio compatibility
  service available. Mika does not change the audio stack or install OS packages.
- **WSL:** use the Linux installer. WSLg/host audio input and Windows microphone
  permission must work; an input-device listing alone does not prove capture.
- **Windows:** enable microphone access for desktop apps and select the correct input.

`mika --help` shows controls and the model location; `mika --version` shows the
installed version. Status uses a single transient stderr line, including in classic
Windows consoles. When stderr is redirected, routine status is omitted; errors and
first-download consent remain visible as text. Only the transcript goes to stdout.

The model is English-only and may produce lowercase, unpunctuated text. There are
no partial transcripts, timestamps, translation, diarization, or transcript history.
Cancellation during synchronous loading/inference may wait for that operation to
return; cancelled work never prints a partial transcript.

## Updating and repairing

Rerun the README's installer to check the latest stable release. A small checksum
file is fetched first. Matching archive identity plus a successful binary startup
check skips the large download and replacement. Missing command/PATH entries are
repaired even when the application is current. This is not a complete integrity
scan of every installed library; use forced reinstallation to repair damaged files:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | MIKA_REINSTALL=1 bash
```

```powershell
$env:MIKA_REINSTALL = '1'
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
Remove-Item Env:MIKA_REINSTALL
```

New archives are checksum-verified, extracted into a scratch directory, and checked
before and after moving into place. An update failure restores the previous app;
if restoration itself fails, recovery files are retained rather than deleted.
Concurrent installers are rejected. Close Mika before updating, especially on Windows.
Model files are stored separately and are never removed by application updates.
There is no background updater or automatic network check when you launch Mika.

Advanced environment variables, identical on both installers:

| Variable | Purpose |
| --- | --- |
| `MIKA_VERSION` | Explicit release tag, e.g. `v0.1.2`, instead of latest. Can deliberately select an older version. |
| `MIKA_REINSTALL=1` | Force a clean reinstall even when the release is current. |
| `MIKA_ARCHIVE_PATH` | Use a local platform archive with an adjacent `.sha256` file. |

Manual archives are on [GitHub Releases](https://github.com/nochinsky/mika/releases).
No installation step downloads model weights or opens the microphone. You can
inspect either installer before executing it. Release archives are not independently
signed; adjacent checksums detect corruption, not a compromised publisher.
No machine-wide PowerShell execution-policy change is made.

## Paths and removal

| Platform | Application | Model cache |
| --- | --- | --- |
| Linux / WSL | `${XDG_DATA_HOME:-$HOME/.local/share}/mika/app` | Same parent, `models/` |
| Windows | `%LOCALAPPDATA%\Mika\app` | `%LOCALAPPDATA%\Mika\models` |

Linux creates `~/.local/bin/mika` and a marked PATH block in your shell profile
(or a Fish `conf.d/mika.fish` file). Relative/empty `XDG_DATA_HOME` falls back to
`~/.local/share`. Windows adds the app's `bin` directory to your user PATH.

To uninstall, remove `app` and the Linux command symlink or Windows user-PATH entry.
Remove `models` only if you also want to reclaim its download. Linux's marked Mika
PATH block may be removed, but `~/.local/bin` is commonly useful for other apps.
A small empty `.installer.lock` file may remain; it does not mean anything is running.

## Model and privacy

The fixed model is **Granite Speech 5.0 470M TurboCTC Q4_K_M**, the standard
**Apache-2.0** variant—not `-nc`. Exact size, immutable revision and SHA-256 are in
[`src/model.h`](../src/model.h). Model updates are deliberate source changes,
not a background download of a moving model version.

Every launch verifies the model's size and checksum. Its initial download requires
consent, HTTPS/certificate validation, bounded transfers and verified atomic
replacement. Failed transfers are discarded. A forcibly killed download can leave
`.part.*` files; remove them only when no download is running. The model directory
may retain `.download.lock` for locking. `CURL_CA_BUNDLE` can name a trusted PEM
bundle for a private/corporate CA without disabling verification.

Audio remains in memory. Recording automatically finishes and transcribes at
**5 minutes**; Enter finishes sooner. The float32 recording buffer is bounded at
19.2 MB, but model/inference memory is substantially larger and grows with audio
length. Transcription starts after recording stops, so longer recordings take more
time and memory to process. A five-minute repeated-public-speech input is covered
by opt-in model tests; this is not a long-form accuracy benchmark. Sessions beyond
five minutes still need a separate chunking/boundary design rather than an
unbounded buffer.

Exit codes: **0** success/help/version; **1** failure; **2** invalid arguments;
**130** cancellation or declined model download.

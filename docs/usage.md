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

Speech recognition is English-only. Mika adds offline punctuation/capitalization
by default; `mika --raw` prints the unformatted ASR transcript instead. Formatting
preserves words/order and obvious literals, but is not an editor and cannot fix
misheard words. Unsupported text or ordinary formatting errors retain the raw text
with a short stderr warning. See [formatting details](punctuation.md).
A mandatory CPU speech classifier checks the whole recording before ASR, including
with `--raw`. Zero detected speech returns exit 3 with no transcript. It does not
trim audio or finish recording automatically when you pause. Background speech,
music or an unusual noise can still fool a classifier; success is not evidence
that Mika heard the intended words. Check important constraints before use.
There are no partial transcripts, timestamps, translation, diarization, or history.
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
The separately cached speech model is never removed by application updates.
Formatting and speech-detection data/runtime remain bundled with the app and are
replaced with it. Missing/damaged speech-detection data fails closed with exit 1;
reinstall the app rather than bypassing the check.
There is no background updater or automatic network check when you launch Mika.

Advanced environment variables, identical on both installers:

| Variable | Purpose |
| --- | --- |
| `MIKA_VERSION` | Explicit release tag, e.g. `v0.2.0`, instead of latest. Can deliberately select an older version. |
| `MIKA_REINSTALL=1` | Force a clean reinstall even when the release is current. |
| `MIKA_ARCHIVE_PATH` | Use a local platform archive with an adjacent `.sha256` file. |

Manual archives are on [GitHub Releases](https://github.com/nochinsky/mika/releases).
Archives include fixed formatting weights/runtime and a 1.24 MB CPU speech
classifier, but not the 279 MB Granite ASR model. Installers never open a microphone or separately fetch the speech model.
You can inspect either installer before executing it. Release archives are not independently
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

## Uninstalling

Close Mika and run the matching command as your normal user, without sudo/admin:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.sh | bash
```

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.ps1 | iex
```

Both show what will be removed and ask once before making changes. Default/Enter
cancels. Linux reads confirmation from the controlling terminal, not the piped
script. Noninteractive use requires explicit unattended consent.

Removal includes the **installer-managed application** (bundled formatter,
speech classifier, runtime, docs/licenses), the fixed downloaded speech model and its `.part.*` files, and the
Mika command/PATH setup. Linux removes only a symlink pointing to this installation,
unchanged Mika blocks in supported shell profiles, and an unchanged Mika Fish file.
Windows removes only the matching application `bin` entry from user/current-process
PATH; it does not modify machine-wide PATH. Restart other terminals afterward.

Uninstallers never delete shared directories such as `~/.local/bin`, unrelated
commands/cache files, source/manual installations, or transcripts saved outside
the managed app directory. The entire managed app directory is removed, so move
any personal files out of it first. App
ownership is checked using the release `VERSION` and installer `ARCHIVE_SHA256`
markers; linked app/cache roots or invalid markers are refused. Linux leaves
symlinked shell profiles and customized Mika profile/Fish content unchanged for
manual review. Unknown files and installer recovery directories are preserved;
coordination locks may remain alongside retained data. Repeating removal is safe.
Use the same XDG/Zsh configuration environment that was used to install Mika to
find custom locations; uninstallers do not search arbitrary directories.

To remove the app but **keep downloaded speech weights**:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.sh | MIKA_KEEP_MODEL=1 bash
```

```powershell
$env:MIKA_KEEP_MODEL = '1'
irm https://raw.githubusercontent.com/nochinsky/mika/main/uninstall.ps1 | iex
Remove-Item Env:MIKA_KEEP_MODEL
```

`MIKA_UNINSTALL_YES=1` explicitly skips confirmation for deliberate unattended use;
`MIKA_KEEP_MODEL` and `MIKA_UNINSTALL_YES` accept only `0` or `1`. Downloaded local
scripts also support `bash uninstall.sh --keep-model --yes` and
`powershell.exe -File uninstall.ps1 -KeepModel -Yes`. No execution-policy change is
needed for the piped PowerShell command. If a process/permission error interrupts
removal, close Mika, correct the reported problem, and rerun; filesystem/PATH
changes are not a single atomic transaction. If the ownership markers themselves
are missing/damaged, inspect the reported app directory and clean it up manually
rather than bypassing ownership checks.

## Model and privacy

The fixed model is **Granite Speech 5.0 470M TurboCTC Q4_K_M**, the standard
**Apache-2.0** variant—not `-nc`. Exact size, immutable revision and SHA-256 are in
[`src/model.h`](../src/model.h). Model updates are deliberate source changes,
not a background download of a moving model version.

Every dictation launch verifies the ASR model's size and full checksum, and also
the bundled Silero VAD's pinned size/SHA-256 ([metadata](../src/speech_asset.h)).
Speech admission uses the native CPU library; no extra runtime Python, download,
model cache or user setting is involved. Its separate MIT/provenance notice is
included with the app. The Granite model's initial download requires
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

## Scripting contract

| Exit | Meaning | stdout |
| --- | --- | --- |
| **0** | Transcript (formatted or safe raw fallback), help, or version | Requested text |
| **1** | Failure | Empty during dictation |
| **2** | Invalid arguments | Empty |
| **3** | No detected speech or empty/whitespace-only ASR output | Empty |
| **130** | Cancellation or declined model download | Empty |

A formatting fallback is still a successful transcript, not an empty/error result.
For an agent wrapper, check success before using any output. Exit 0 is not a
confidence score or approval to execute a prompt unattended. For example:

```sh
if prompt="$(mika)"; then
    # Pass "$prompt" to your preferred agent here.
    printf '%s\n' "$prompt"
fi
```

```powershell
$text = mika
if ($LASTEXITCODE -eq 0) {
    # Pass $text to your preferred agent here.
    $text
}
```

No agent command, clipboard action, or automatic submission is built into Mika.
As with other CLIs, an output-device failure can occur after a write has started;
check the exit status, not just whether stdout contains bytes.

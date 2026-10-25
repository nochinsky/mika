# Usage and troubleshooting

For installation, updates and removal commands, start with the [README](../README.md).
Mac first-run security approval is covered in [Mac support](macos.md#first-run-security-approval).

## Recording and output

Run `mika`, speak after **Listening**, and press **Enter** to finish. Esc/Ctrl+C
cancels. The recording limit is five minutes; pauses do not automatically finish
recording. A controlling terminal is required even when stdout is redirected.
SSH does not forward a microphone automatically.

Choose the default input in your OS sound settings:

- **Mac:** allow your terminal under Privacy & Security → Microphone.
- **Linux:** ensure your ALSA/PulseAudio-compatible input works. PipeWire systems
  need the usual PulseAudio compatibility service and `libpulse` where used.
- **Windows:** enable microphone access for desktop apps.

Mika does not select a different input or change OS sound settings. Linux under
WSL also requires working host/WSLg audio routing and Windows permissions; a device
listing alone does not prove capture.

`mika --help` lists controls and the model path. `mika --version` shows the installed
version. Only the transcript goes to stdout; status and errors go to stderr.
Routine status is omitted when stderr is redirected. Cancellation during synchronous
loading/inference may wait for it to return, but never prints a partial transcript.

## Recognition and formatting

Recognition is English-only. `--raw` skips punctuation/capitalization, not speech
admission. A mandatory CPU classifier checks the whole recording before ASR without
trimming, rescaling or automatically stopping it. No detected speech returns exit 3.
Missing/damaged speech-detection data returns exit 1; reinstall rather than bypass it.

Formatting preserves recognized words/order and obvious literals. Unsupported text,
load failures and rejected formatting keep the raw transcript with a warning.
Since v0.3.2, loader failures include a bounded escaped native error on stderr;
these can contain local paths, not dictated text. Earlier releases report only
the generic runtime warning. See [formatting behavior](punctuation.md).

Neither speech admission nor exit 0 guarantees the intended speaker, accurate
recognition or preserved meaning. Review commands, identifiers, versions, numbers
and negations. There are no partial transcripts, translation, diarization or history.

## Updating and repairing

Close Mika and rerun the platform installer from the README. It checks the latest
release, keeps the separate speech model, and repairs command/PATH setup. Matching
archive identity and successful startup skip replacement; this is not a full
integrity scan of every installed file. Force repair with `MIKA_REINSTALL=1`.

New archives are HTTPS/checksum-verified and staged before replacement. Failed
updates restore the previous app; failed recovery preserves its files. Concurrent
maintenance is rejected. No background updater or runtime update check is installed.
Formatting and VAD data are bundled and replaced with the app.

| Variable | Purpose |
| --- | --- |
| `MIKA_VERSION` | Select a release tag, such as `v0.3.2`, instead of latest. |
| `MIKA_REINSTALL=1` | Force app reinstallation, retaining the speech model. |
| `MIKA_ARCHIVE_PATH` | Use a local platform archive and adjacent `.sha256`. |

For shell installers, put options on `bash`, for example:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | MIKA_REINSTALL=1 bash
```

Use `install.sh` instead for Linux. In PowerShell, set the environment variable
before invoking the installer and remove it afterward:

```powershell
$env:MIKA_REINSTALL = '1'
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
Remove-Item Env:MIKA_REINSTALL
```

Inspect scripts before running them if desired. Adjacent checksums detect
corruption, not a compromised publisher. Mac releases are ad-hoc signed, not
notarized. No installer opens a microphone, downloads Granite without first-run
consent, changes global PowerShell execution policy or disables OS security.

## Installation paths

| Platform | Application | Speech model cache |
| --- | --- | --- |
| Mac | `~/Library/Application Support/Mika/app` | Same parent, `models/` |
| Linux | `${XDG_DATA_HOME:-$HOME/.local/share}/mika/app` | Same parent, `models/` |
| Windows | `%LOCALAPPDATA%\Mika\app` | `%LOCALAPPDATA%\Mika\models` |

Mac/Linux create `~/.local/bin/mika` and managed shell PATH configuration. Relative
or empty Linux `XDG_DATA_HOME` falls back to `~/.local/share`; Mac does not use it.
Windows adds the app's `bin` directory to user PATH. Restart other terminals after
PATH changes. Use the same XDG/Zsh configuration environment for installation and
removal; scripts do not search arbitrary locations.

## Uninstalling

Use the [README's platform command](../README.md#uninstall). Removal asks once;
Enter/default cancels. Shell scripts read confirmation from the controlling
terminal, not piped stdin. Set `MIKA_KEEP_MODEL=1` to keep downloaded Granite weights:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | MIKA_KEEP_MODEL=1 bash
```

Use `uninstall.sh` for Linux. In PowerShell, set `$env:MIKA_KEEP_MODEL = '1'`, run
`uninstall.ps1`, then remove that environment variable. `MIKA_UNINSTALL_YES=1`
explicitly permits unattended removal; both variables accept only `0` or `1`.
Local shell scripts also accept `--keep-model --yes`; PowerShell uses `-KeepModel -Yes`.

Removal deletes the installer-managed app, fixed model/partial downloads and
matching command/PATH setup. Ownership markers are required. Shared directories,
unrelated data, customized/linked shell configuration and recovery files are
preserved. Files outside the app are not removed; move personal files out of the
managed app before uninstalling. Source/manual installations are not managed.

If interrupted, close Mika, correct the reported problem and rerun. Removal is not
one atomic filesystem/PATH transaction. Do not bypass missing ownership markers;
inspect the reported location manually. Mac maintenance-lock recovery is described
[in its guide](macos.md#installation-layout-and-recovery).

## Models and privacy

The fixed recognizer is **Granite Speech 5.0 470M TurboCTC Q4_K_M**, the Apache-2.0
variant, not `-nc`. Exact size, revision and SHA-256 are in
[`src/model.h`](../src/model.h); bundled Silero identities are in
[`src/speech_asset.h`](../src/speech_asset.h). Every dictation launch verifies their
complete sizes/checksums. Formatting data is verified when used.

The initial Granite download requires consent, HTTPS/certificate validation,
bounded transfer and verified atomic replacement. Failed transfers are discarded;
a forcibly killed download can leave `.part.*` files. Remove them only when no
download is running. `.download.lock` may remain for coordination. `CURL_CA_BUNDLE`
can select a trusted corporate/private PEM bundle without disabling verification.

Audio stays in memory. The five-minute float buffer is bounded at 19.2 MB;
model/inference memory is larger and grows with recording length. Transcription
starts after capture stops. There is no saved-audio runtime mode, upload or telemetry.
Developer recording tools require separate explicit consent.

## Scripting contract

| Exit | Meaning | stdout |
| --- | --- | --- |
| **0** | Transcript, safe raw fallback, help or version | Requested text |
| **1** | Operational/integrity failure | Empty during dictation |
| **2** | Invalid arguments | Empty |
| **3** | No detected speech or empty recognition | Empty |
| **130** | Cancellation or declined model download | Empty |

A formatting fallback remains success. Since v0.3.2, detected
terminal read failures return 1 rather than cancellation, and broken pipes do not
bypass terminal cleanup. Failed transcript writes return 1. Check the exit status,
not just output bytes: an output-device failure can occur after writing begins.
For example:

```sh
if text="$(mika)"; then
    printf '%s\n' "$text"
fi
```

Mika never executes or submits dictated instructions. Exit 0 is not a confidence
score or approval for unattended execution.

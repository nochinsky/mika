# Usage and troubleshooting

Install, update and uninstall commands are in the [README](../README.md). If you're
on a Mac and it won't open, start with [Mac first-run approval](macos.md#first-run-security-approval).

## Recording

Run `mika`, wait for **Listening**, talk, and press **Enter**. **Esc** or **Ctrl+C**
cancels without printing anything.

Recording only stops when you press Enter. Pausing won't end it. The one exception
is the five-minute limit: when you reach it, Mika stops and transcribes what it has.

Mika needs a real terminal to read your keypresses, even when you redirect its
output. Over SSH, keep in mind that your microphone isn't forwarded to the remote
machine.

## Microphone problems

Mika always records from your system's default input. To use a different mic,
change the default in your OS settings. Mika won't change any sound settings itself.

- **Mac:** allow your terminal app under System Settings → Privacy & Security → Microphone.
- **Linux:** your input needs to work through ALSA or PulseAudio. On PipeWire, that
  means having the PulseAudio compatibility layer running (and `libpulse` installed
  where needed).
- **Windows:** turn on microphone access for desktop apps in Privacy settings.
- **WSL:** audio has to make it from Windows into WSL (WSLg handles this) and Windows
  has to allow microphone access. Seeing the device listed doesn't mean capture works.

If Mika says *no audio is arriving from the microphone*, it got no sound at all
for five seconds. That almost always means the wrong default device or a missing
permission.

## Output

Only the transcript goes to stdout. Status lines and errors go to stderr, and the
status lines are hidden when stderr is redirected.

`mika --help` shows the controls and where the model is stored.
`mika --version` shows the installed version.

If you cancel while Mika is loading the model or transcribing, it finishes that step
before quitting, which can take a moment. You never get a partial transcript.

## Recognition and formatting

Before transcribing, Mika runs a small speech detector over the whole recording. If
it hears no speech, you get exit code 3 and no text. The detector doesn't cut or
change your audio. It only decides whether to go ahead. `--raw` doesn't skip it.
If the detector's data is missing or damaged, Mika stops with exit 1. Reinstall to fix it.

After transcription, Mika adds punctuation and capitals. This step only adds
punctuation and capitals. It doesn't fix misheard words, change word order or
"correct" things like file names and numbers. If formatting fails or produces
something suspicious, you get the raw transcript and a warning on stderr. Since
v0.3.2 that warning can include the underlying error message, which may contain
file paths (never your dictated text). More detail is in
[how formatting works](punctuation.md).

What Mika doesn't do: translation, speaker labels, live partial results or history.

It also can't promise it heard you correctly. A successful run means it produced
text, not that the text is right. Read it over, especially names, numbers, versions,
negations ("can" vs "can't") and anything you're about to run.

## Updating and repairing

Close Mika and run the install command from the README again. It fetches the latest
release, keeps your downloaded model, and fixes the `mika` command and PATH if
they've been broken.

If the installed version already matches and starts fine, the installer leaves it
alone. It doesn't check every file, so if something seems broken, force a reinstall
with `MIKA_REINSTALL=1`.

Downloads are checked against a SHA-256 checksum and set up beside the existing app
before replacing it. If an update fails, your previous version is restored. If that
also fails, its files are kept so nothing is lost. Two installs can't run at once.
Nothing updates in the background, and Mika never checks for updates when you run it.
The formatting and speech-detection data ship with the app and update along with it.

| Variable | What it does |
| --- | --- |
| `MIKA_VERSION` | Install a specific release, like `v0.3.2`, instead of the latest. |
| `MIKA_REINSTALL=1` | Reinstall the app even if it looks up to date. Keeps the model. |
| `MIKA_ARCHIVE_PATH` | Install from a local archive. Its `.sha256` file must sit next to it. |

With the shell installers, put the variable just before `bash`:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | MIKA_REINSTALL=1 bash
```

(Use `install.sh` on Linux.) In PowerShell, set it, run the installer, then clear it:

```powershell
$env:MIKA_REINSTALL = '1'
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
Remove-Item Env:MIKA_REINSTALL
```

You're welcome to read the scripts before running them. Note that the checksum
catches a corrupted download. It can't protect you if the release itself was
tampered with. The Mac builds are ad-hoc signed, not notarized.

The installers never open your microphone, never download the speech model without
asking first, never change your PowerShell execution policy, and never turn off
OS security features.

## Where things are installed

| Platform | App | Speech model |
| --- | --- | --- |
| Mac | `~/Library/Application Support/Mika/app` | `~/Library/Application Support/Mika/models` |
| Linux | `${XDG_DATA_HOME:-$HOME/.local/share}/mika/app` | `…/mika/models` (same parent) |
| Windows | `%LOCALAPPDATA%\Mika\app` | `%LOCALAPPDATA%\Mika\models` |

On Mac and Linux the installer creates `~/.local/bin/mika` and adds it to your
shell's PATH. On Windows it adds the app's `bin` folder to your user PATH. Open a
new terminal after installing so the change takes effect.

On Linux, an empty or relative `XDG_DATA_HOME` is ignored and `~/.local/share` is
used instead. The Mac ignores `XDG_DATA_HOME`. Run install and uninstall with the
same XDG and Zsh settings so the uninstaller finds what the installer created. It
only looks in those locations.

## Uninstalling

Use the [uninstall command for your platform](../README.md#uninstall). It asks once
before deleting anything. The default answer is no, so just pressing Enter cancels.
The shell scripts read your answer from the terminal, so piping `yes` into them won't work.

To keep the downloaded speech model, set `MIKA_KEEP_MODEL=1`:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | MIKA_KEEP_MODEL=1 bash
```

(Use `uninstall.sh` on Linux.) In PowerShell, set `$env:MIKA_KEEP_MODEL = '1'`, run
`uninstall.ps1`, then clear the variable.

To uninstall without the prompt, for example in a script, set `MIKA_UNINSTALL_YES=1`.
Both variables accept only `0` or `1`. If you've downloaded the scripts locally,
you can use `--keep-model --yes` instead, or `-KeepModel -Yes` in PowerShell.

**What gets removed:** the app, the speech model (plus any half-finished downloads),
and the `mika` command and PATH entries the installer added.

**What's left alone:** shared folders, anything Mika didn't create, shell config
you've customized or symlinked, and recovery files. Mika only deletes folders that
carry its own ownership marker. If you've saved personal files inside the app
folder, move them out first. Builds from source or manual copies aren't managed
by the uninstaller.

If removal gets interrupted, close Mika, fix whatever it reported, and run it again.
It can't undo half a removal in one go. If it complains about a missing ownership
marker, don't work around it. Look at the folder it names and decide for yourself.
On a Mac, a leftover maintenance lock is covered in the
[Mac guide](macos.md#installation-layout-and-recovery).

## Models and privacy

Speech recognition uses **Granite Speech 5.0 470M TurboCTC Q4_K_M**, the Apache-2.0
licensed version (not the non-commercial `-nc` one). Its exact size, revision and
SHA-256 are in [`src/model.h`](../src/model.h). The bundled Silero speech detector
is pinned in [`src/speech_asset.h`](../src/speech_asset.h). Mika checks both against
their size and checksum every time it starts. The formatting data is checked when
it's loaded.

The model download only starts after you agree. It uses HTTPS with certificate
checks, has a size limit, and is verified before being moved into place. A failed
download is thrown away. If the process is killed mid-download, `.part.*` files may
be left behind. You can delete them once no download is running. A `.download.lock`
file may also stick around. That's normal. If you're behind a corporate proxy with
its own certificates, point `CURL_CA_BUNDLE` at your PEM bundle. Verification stays on.

Your audio is kept in memory only. Five minutes of audio takes at most 19.2 MB.
The model itself uses more, and that grows with longer recordings. Transcription
starts after you stop recording. Mika has no mode that saves audio, and it never
uploads anything or sends telemetry. The developer recording tools in `scripts/`
are separate and ask for their own permission.

## Using Mika in scripts

| Exit code | Meaning | stdout |
| --- | --- | --- |
| **0** | Got a transcript (possibly unformatted), or printed help/version | The text |
| **1** | Something went wrong | Empty |
| **2** | Bad arguments | Empty |
| **3** | No speech detected, or nothing recognized | Empty |
| **130** | Cancelled, or you declined the model download | Empty |

If formatting fails but transcription worked, that's still exit 0. You just get
the raw text. Since v0.3.2, losing the terminal returns 1 rather than 130, and a
closed pipe no longer leaves your terminal in a weird state. If writing the
transcript fails, you get exit 1. Some text may already have been written by then,
so check the exit code rather than whether you got output:

```sh
if text="$(mika)"; then
    printf '%s\n' "$text"
fi
```

Mika never runs anything you say. A zero exit code means "here's some text", not
"this is safe to execute".

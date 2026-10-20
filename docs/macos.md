# Mac support

Mika supports **Apple Silicon ARM64 on macOS 14 or later**, experimentally.
Intel Macs, Rosetta execution and universal binaries are not supported. Speech
recognition and formatting run on the CPU; no Metal/GPU/Core ML inference is used.

## Install, update and remove

Install as your normal user, without sudo, Homebrew, Python or a compiler:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | bash
```

Close Mika and rerun the command to update. Restart your terminal if `mika` is not
found. Run `mika --version` to check the installed version, then `mika` to dictate.
Choose the default input in macOS sound settings. Your terminal may need access
under **System Settings → Privacy & Security → Microphone**.

Remove the managed application and downloaded speech model, with confirmation:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | bash
```

Set `MIKA_KEEP_MODEL=1` on the removal command to retain the speech model. Set
`MIKA_REINSTALL=1` on the installation command to force repair. Shared version,
local-archive and unattended-removal options are in [the usage guide](usage.md).

Downloads are available on [GitHub Releases](https://github.com/nochinsky/mika/releases)
as `mika-macos-arm64.tar.gz` with an adjacent `.sha256`. For a local archive, save
both files and the same release's `install-macos.sh`, then run:

```sh
MIKA_ARCHIVE_PATH="$HOME/Downloads/mika-macos-arm64.tar.gz" bash install-macos.sh
```

The archive includes formatting and speech-detection data, not the 279 MB Granite
speech model. Its first download requires separate consent. For fully offline
use, that verified model must already be present.

## First-run security approval

The executable and formatter libraries are **ad-hoc signed**, not Developer
ID-signed or notarized. macOS can block downloaded code before it runs. Mika may
be terminated, or recognition may work while formatting reports that its runtime
is unavailable. A blocked library is one possible cause, not every loader failure.

If the warning is about an unidentified developer or software Apple cannot verify,
and you have independently decided to trust the official release:

1. Attempt to run Mika and read the exact macOS warning and blocked filename.
2. Open **System Settings → Privacy & Security**, then scroll to **Security**.
3. Use **Open Anyway** for that specific trusted item and confirm the system prompt.
4. Run Mika again. A formatter library may require its own approval:
   `libonnxruntime.dylib` or `libmika-fullstop.dylib`.

**Do not override a warning that software is damaged, contains malware or will
harm your Mac.** Stop and investigate instead. Checksums detect corruption, not a
compromised publisher. See [Apple's security guidance](https://support.apple.com/en-us/102445)
for the distinction between these warnings and per-item approval.

Approval is normally remembered for the approved copy. A replacement or update
can require approval again. Mika does not disable Gatekeeper, strip quarantine,
change security policy or approve code automatically.

Current source identifies the failing library/export and reports a bounded native
loader error on stderr; Windows uses the native error code. Diagnostic controls
and non-ASCII bytes are escaped. Messages can contain local filesystem paths, but
never dictated text or inference exception contents. Review paths before sharing
logs. These diagnostics require a build containing the change; v0.3.1 has only the
generic runtime warning. Missing/damaged libraries require repair, not security
approval; damaged speech-detection data remains a hard error even with `--raw`.

## Installation layout and recovery

| Item | Location |
| --- | --- |
| Application | `~/Library/Application Support/Mika/app` |
| Speech model | `~/Library/Application Support/Mika/models` |
| Command | `~/.local/bin/mika` |

The installer configures Zsh/Bash or Fish PATH entries. Mac data paths do not use
`XDG_DATA_HOME`. Archives are HTTPS/checksum-verified and restricted to regular
files/directories under `mika/`. Failed updates restore the previous app; failed
recovery retains its files. Updates preserve the separate speech model.

Installation/removal uses stock Bash 3.2 and BSD utilities, coordinated through
`~/Library/Application Support/Mika/.maintenance-lock`. Close Mika first. After a
forcibly terminated installer, verify no maintenance process is running before
removing **only the empty lock directory** and retrying. Removal preserves unknown
data, modified shell configuration and recovery directories. Move any personal
files out of the managed app before removal.

## Validation status

Native ARM64 CI covers CPU backend selection, signatures/dependencies, terminal
fixtures, real-file raw/formatted inference, five-minute processing, installed and
relocated execution, and install/remove transactions. It does not reproduce every
microphone, desktop permission state or browser-download security prompt.

A physical-Mac tester reported successful capture, recognition and punctuation,
with repeated launches working after manual Privacy & Security approval. This is
a **reported smoke test**, not a complete acceptance run: exact OS/input/artifact
metadata, timings and permission-denial/recovery results were not collected.

Before promoting support beyond experimental, record the OS, terminal, input and
artifact identity and complete:

- [ ] Fresh browser download, checksum/signature checks and security approvals.
- [ ] Per-user install/PATH and model-download decline/accept behavior.
- [ ] Microphone permission deny, recovery and allow; correct default input.
- [ ] Natural dictation, pauses, quiet speech and silence; meaning/number review.
- [ ] Enter timing, Esc/Ctrl+C, exit codes, redirected stdout and terminal recovery.
- [ ] Update, forced repair, keep-model/full removal and interrupted recovery.

Developer ID signing and notarization remain unimplemented and require Apple
developer credentials. A polished distribution must sign the executable and both
formatter libraries and follow [Apple's notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).
Ad-hoc signatures are not equivalent. Build instructions are in
[CONTRIBUTING.md](../CONTRIBUTING.md); automated package checks are in
[`scripts/check_macos_package.py`](../scripts/check_macos_package.py).

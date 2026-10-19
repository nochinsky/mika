## Mika v0.3.1 — Apple Silicon downloads and safer dictation

Run `mika`, speak, press Enter, get text, exit. CPU-only, offline after the consented
first Granite download; no account, cloud cleanup, daemon or end-user Python.

### macOS is now publicly downloadable — experimental

This release includes **`mika-macos-arm64.tar.gz` and its SHA-256**, alongside the
Linux and Windows downloads. Target: **native Apple Silicon ARM64, macOS 14+**.
Intel/Rosetta, universal binaries and GPU/Metal/Core ML inference are not supported.

Install/update without sudo, Homebrew or developer tools:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | bash
```

Remove the managed app/model/PATH setup, with confirmation:

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/uninstall-macos.sh | bash
```

`MIKA_KEEP_MODEL=1` keeps downloaded Granite weights during removal.
`MIKA_REINSTALL=1` forces app repair. `MIKA_VERSION=v0.3.1` pins this release.
See the [Mac guide](https://github.com/nochinsky/mika/blob/v0.3.1/docs/macos.md)
for paths, permissions, manual archives and recovery.

**Experimental means:** native hosted ARM64 CPU builds, public-file inference,
console controls, stock-Bash install/remove, relocation, backend/dependency and
ad-hoc-signature audits pass. A physical Mac's microphone permissions/capture,
audio routing and downloaded-artifact Gatekeeper behavior have **not** been
accepted. Binaries are **ad-hoc signed, not Developer ID-signed/notarized**. No
installer strips quarantine or disables OS security. Public availability is not
stable Mac certification; please report real-device results with OS/terminal/input.

### Reliability changes on all platforms

- Mandatory verified CPU speech admission, also in `--raw`, before ASR. This rejects
  the silence/noise/tone false-success regressions; it does not guarantee that all
  noise/music is rejected or that recognized speech belongs to the intended speaker.
- Missing/corrupt bundled VAD data fails closed; Granite, VAD and formatting weights
  retain full integrity checks. VAD adds about 1.24 MB; Granite remains separate.
- Conservative formatting rejection for a new internal sentence break immediately
  after an English negation or its next word. Rejected formatting keeps original
  raw text with a warning. This is not a semantic parser or an ASR correction.
- Safe per-user Linux/Windows/Mac removal, ownership checks, explicit keep-model
  support and recovery preservation. Updates keep the separate Granite cache.
- Cross-platform release metadata: archives now write identical LF `VERSION`
  files, while publication accepts exact-tag LF or Windows CRLF metadata. The
  attempted v0.3.0 publication stopped at this overly strict check; no partial
  release was made public and the original tag was not rewritten.
- Shared executable-relative asset paths/offline verification, expanded native and
  model-free tests, five-minute regressions, and private opt-in developer validation
  tools. The installed application still never saves audio.

### Expectations and installation

Speech recognition can mishear technical words, identifiers, version strings,
numbers and negations. Formatting preserves transcript words, not guaranteed intent.
Review important instructions; exit 0 is not confidence or unattended-execution
approval. No spelling guesses, model menus or LLM rewrite have been added.

Linux/WSL x86-64 (glibc 2.35+):

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

Windows 10/11 x64, PowerShell:

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

Close Mika and rerun the platform installer to update; check `mika --version`.
Formatting and VAD assets are bundled. The **279 MB Apache-2.0 Granite model** is a
separately consented first-run download, reused across updates. Audio remains in
memory; Enter, Esc/Ctrl+C, five-minute limit and stdout redirection are unchanged.

All three platform package jobs, model-free regressions and native uninstaller
checks gate publication. Exactly three archives plus three matching checksums are
required before the draft becomes public/latest. No private audio, transcripts,
ASR cache, developer Python environment or validation executables are packaged.
Checksums detect corruption, not a compromised publisher.

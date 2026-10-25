## Mika v0.3.2 — terminal recovery and clearer diagnostics

This patch ships the reliability fixes developed after v0.3.1 for the offline
English dictation CLI.

### Runtime fixes

- Treat a lost controlling terminal as an operational failure (exit 1), including
  during loading, recognition, formatting and model download. User cancellation
  still returns 130 and publishes no transcript.
- Preserve terminal cleanup when output pipes close on Linux/macOS. Broken pipes
  become handled write failures instead of interrupting cleanup with SIGPIPE.
- Consume queued cancellation keys during model download and discard incomplete
  downloads on terminal failure.
- Identify a failing formatter library/export with a bounded native loader
  diagnostic. Controls and non-ASCII bytes are escaped; diagnostics exclude
  dictated text and inference exception contents. Local paths may appear.
  Formatting failures continue to keep the raw transcript with a warning.

### Build and distribution

- Bound and consolidate build-time asset preparation, kill/reap timed-out workers
  and retain recovery files if publication rollback fails.
- Reject empty runtime files, linked executable/library roots, Windows junctions
  and incomplete formatter notice inventories when packaging.
- Validate all three platform archives, their checksums and embedded versions
  together on ordinary CI runs before the separately gated tag publication.
- Expand terminal, download, packaging and asset-preparation regressions and
  clarify usage, validation and platform documentation.

### Update

Close Mika and rerun your platform's installer:

**Windows — PowerShell**

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

**Linux — x86-64, glibc 2.35+**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

**Mac — experimental Apple Silicon ARM64, macOS 14+**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install-macos.sh | bash
```

The downloaded Granite speech model is reused. Check the update with
`mika --version`, which should print `mika 0.3.2`.

Recognition can still mishear names, numbers and negations; review important
output. Mac support remains experimental, and binaries remain ad-hoc signed
rather than Developer ID-signed/notarized. See the
[Mac guide](https://github.com/nochinsky/mika/blob/v0.3.2/docs/macos.md) for security
approval and hardware acceptance limits. This patch does not establish a new
natural-dictation accuracy benchmark.

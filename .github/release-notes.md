## Mika v0.2.0 — quick prompts, with offline punctuation

Mika still does one thing: run `mika`, speak, press Enter, get text, exit.

### Changes

- **Offline punctuation/capitalization is now the default**, using English
  FullStop INT8 after the unchanged Granite speech model.
- **`mika --raw`** skips formatting. No model menus, configuration wizard,
  background service, cloud cleanup or end-user Python dependency.
- Formatting renders onto original words, protects obvious literals (including
  paths, emails, identifiers and acronyms), and independently rejects word changes.
  Ordinary formatting failures keep raw text with a short stderr reason.
- **No speech now exits 3 with empty stdout**, so success-checked agent wrappers
  do not submit an empty prompt. Cancellation still exits 130 without a transcript.
- One production build/test pipeline replaces the experimental build variants.
  Version/asset consistency and prompt-preservation checks help catch maintenance drift.

### Expectations and installation

This is fast English dictation for agent prompting, not publication-ready editing.
Punctuation, names and sentence boundaries can be wrong; speech recognition can
still mishear words. Review important commands/messages. The original authored
prose-style targets remain unmet/advisory; safety checks were not weakened and
reference answers were not changed to make scores pass.

Formatting data/runtime are bundled with the app, so archives are larger. The
existing quantization/preparation method and payload layout are unchanged. The
279 MB Granite model remains a consented first-run download, cached separately and
preserved on updates. Afterwards everything works offline; recordings stay in RAM.

Update using the same command as installation, then check `mika --version`:

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

Supported prebuilts: x86-64 Linux/WSL glibc 2.35+ and Windows 10/11 x64, with
runtime-dispatched speech CPU modules. Five-minute limit, Enter/Esc/Ctrl+C,
quiet UI and stdout redirection are unchanged. Both native platform package jobs
must pass before this tag publishes. See repository docs for tests, benchmark
measurement scopes, limitations and model/dependency notices. No private audio or
validation executables are included in the archives.

## Quieter dictation, cleaner updates

- One updating status line: Starting → Listening → Transcribing. It disappears on
  success, leaving only the transcript. Works without ANSI support in classic
  Windows consoles; redirected logs omit routine status.
- Rerun the same installer to update. Current installations skip the archive
  download; model files are preserved. `MIKA_REINSTALL=1` forces a repair.
- Installer locking prevents competing updates. Failed updates roll back; recovery
  files are kept if automatic restoration fails.
- A shorter README focused on installation and use, with advanced details moved
  into linked documentation.

The **60-second automatic finish remains unchanged**. No microphone recording or
model download happens during installation. On first use, Mika asks before fetching
its fixed 279 MB English model; later runs work offline.

### Install or update

**Linux / Arch / WSL — x86-64, glibc 2.35+:**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

**Windows 10/11 x64 — PowerShell:**

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

Close Mika before updating. Use `mika --version` to check the installed release.

Native Linux/Windows CI validates builds, model download/inference, installation,
updates and failure paths. Terminal tests use fake audio, never a private microphone.
See the [README](https://github.com/nochinsky/mika#readme) for usage.

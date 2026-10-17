## Five-minute recordings

- Record for up to **5 minutes**, instead of 60 seconds.
- The timer now shows `00:00 / 05:00`. Press **Enter** sooner whenever you're done;
  **Esc / Ctrl+C** still cancels. At five minutes, recording automatically finishes
  and transcription starts.
- Same quiet interface, fixed offline model, and clean transcript output.
- Added full-capacity buffer tests and a real-model 300-second input regression
  using repeated public speech. This verifies length handling and speech at the
  end, not general long-form dictation accuracy.

Transcription still starts after recording stops. Longer recordings take more time
and memory; the 19.2 MB recording buffer is only part of total inference memory.
No model re-download is needed when updating from the previous release.

### Install or update

Close Mika, then rerun your installation command.

**Linux / Arch / WSL — x86-64, glibc 2.35+:**

```sh
curl -fsSL https://raw.githubusercontent.com/nochinsky/mika/main/install.sh | bash
```

**Windows 10/11 x64 — PowerShell:**

```powershell
irm https://raw.githubusercontent.com/nochinsky/mika/main/install.ps1 | iex
```

Check with `mika --version`. Application updates preserve the cached model and do
not open the microphone. See the [README](https://github.com/nochinsky/mika#readme)
for usage and advanced installation details.

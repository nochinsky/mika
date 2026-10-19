# Architecture and safety boundaries

Mika is a one-shot English dictation CLI, not a configurable speech platform.
Its contract is **run → speak → Enter → one transcript on stdout → exit**.
There is no daemon, agent submission, clipboard action or saved-audio runtime mode.
v0.3.1 distributes these safeguards on Linux/Windows and includes an experimental
Apple Silicon Mac download. An installed release changes only through explicit
installation/update. Mac distribution is public; physical-Mac acceptance and
Developer ID signing/notarization are not claimed.

## Runtime path

1. `main.c` validates arguments and acquires the controlling terminal. `model.c`
   obtains the fixed Granite ASR path, asks before its first download, and verifies
   its full size/SHA-256 on every dictation launch. Consent is not read from piped
   stdin. `--help`/`--version` do not initialize microphones or ML engines.
2. `engine.c` initializes the pinned CPU backend, verifies/loads the bundled
   Silero VAD and creates the ASR session. Missing or corrupt admission data is a
   hard error, not permission to skip the classifier. Both sessions are CPU-only;
   VAD uses one thread. No extra runtime model download or Python is introduced.
3. `audio.c`/`pcm.c` capture mono 16 kHz float PCM from the system's default input.
   The callback writes into a bounded five-minute buffer. Enter finishes;
   Esc/Ctrl+C cancels. A pause does **not** automatically stop recording.
4. After capture ends, `engine.c` checks the **whole original recording** with
   Silero VAD. The initial operating point is upstream's threshold 0.5 with no
   minimum speech-segment duration, to avoid imposing a long-utterance requirement.
   Zero detected segments returns 3 without running ASR. Malformed/failed results
   return 1. Admission does not trim, concatenate, rescale or replace PCM.
5. Admitted audio is transcribed by the fixed English Granite CPU model.
   Empty/whitespace-only text returns 3. `--raw` skips only the next step; it
   cannot bypass admission. Cancellation/failure never publishes partial ASR text.
6. Default mode passes text to the native FullStop formatter. The renderer and
   final guard preserve transcript words/order and obvious literals. Ordinary
   formatting failure falls back to raw with a warning. A bounded guard rejects
   new internal sentence breaks immediately after a negation or its next word;
   it does not repair ASR words or guarantee semantic accuracy. Invalid/unusable
   output is not silently submitted. Only a successful result reaches stdout.
7. Common cleanup stops capture and frees sessions before their borrowed models,
   restores terminal modes, and exits. Synchronous third-party work can delay
   cancellation until it returns. Audio remains in memory and is never saved.

## Owned modules and dependency boundaries

| Module | Responsibility | Important boundary |
| --- | --- | --- |
| `main.c` | CLI/control flow, cancellation, stdout contract | No automatic agent execution |
| `platform.c` | Terminal, signals, UTF-8 file access, locks/time | Native Windows/POSIX behavior |
| `audio.c`, `pcm.c` | Callback capture, bounded PCM ownership | No file recording/runtime Python |
| `verify.c` | Complete size/SHA-256 validation | Crypto/platform only; no network |
| `model.c` | Consented ASR acquisition and atomic verified publication | Curl lives here, not in formatting |
| `assets.cpp` | Shared executable-relative UTF-8 bundled paths | Reject rooted/traversing suffixes |
| `engine.c` | Verified CPU admission and ASR lifecycle | Pinned native transcribe API |
| `punctuation*.c/.cpp`, `fullstop*.cpp` | Safe formatting, native module/ORT bridge | CPU provider, guarded raw fallback |

The C++ filesystem helper replaces duplicate executable-discovery code; it does
not introduce a general resource registry. The verifier is shared by ASR, VAD and
formatting without linking the downloader into the punctuation/file probe.
There is no evidence for a broad C rewrite or an ASR-compute speedup. New C code
should make an observed policy/ownership boundary clearer, not add configuration.

## What admission does and does not guarantee

Before this safeguard, the real ASR emitted successful nonempty text for digital
silence, two white-noise levels and a steady tone. Checking only blank output was
therefore insufficient. The admission regression now rejects those four inputs
and five additional deterministic noise/tone cases, while retaining five public
speech variants including attenuation and a short utterance surrounded by pauses.

This is **not a guarantee of silence detection or semantic safety**. A classifier
can accept unusual noise/music or speech from the wrong person. Brief/quiet speech
can be missed; admitted speech can be misheard. In public-file attenuation checks,
ASR sometimes lost the word “not” even though admission succeeded. Formatting
preservation cannot repair an ASR error. Review negations, numbers, names and
constraints before treating text as an agent instruction. No confidence score or
unattended execution permission is implied by exit 0.

The default threshold/minimum-duration choice remains provisional pending real
consented dictation evidence. Do not tune on a single speaker/public fixture or
substitute phrase blacklists, energy thresholds or nonempty text for validation.

## Technical dictation limits

The pinned Granite5CTC implementation uses greedy CTC collapse. This family does
not advertise vocabulary/context-prompt or ITN controls: passing generic API
fields does not create technical biasing (unsupported controls are ignored with
an upstream warning). There is no supported beam-search setting here to turn up.
Mixed word/digit version strings and misheard identifiers can therefore originate
in ASR before formatting. FullStop preserves those source tokens; it is not a
version parser or a technical-spelling repair system. Do not add post-hoc
reference alternatives or guessed corrections to make a score improve.

Capture quality is a separate prerequisite. Flat-topped/saturated input loses
information before decoding. Reducing a saved clipped waveform cannot recover
it; good input levels and microphone placement should be checked before changing
models. The explicit saved-audio developer recorder warns about substantial
PCM saturation but never changes the waveform or OS input settings. Neither that
warning nor public-file tests establish an accurate transcript.

## Tests and evidence

- **Model-free:** actual owned core, CLI fixtures and engine policy with fake ML,
  asset-path/full SHA-256 checks, formatting guards, local HTTPS and installer/package
  transactions. No dependency/ML fetch or microphone. ASan/UBSan instruments owned
  code, not all third-party libraries.
- **Full/native:** pinned real headers/backend, native formatter/module lifecycle,
  public raw/default speech, five-minute regression, real admission negatives and
  positives, required-asset damage and installed/relocated inference. CI runs on
  Linux x86-64, Windows x64 and experimental macOS ARM64.
- **Human/hardware:** opt-in default-input capture, meaning/correction review on
  fixed natural prompts, actual Enter-to-output timing and desktop permission/trust
  behavior. These cannot be inferred from fake devices or public-file inference.

See [reproducible validation](validation.md), the [dated laptop measurements](laptop-validation.md),
and the [experimental Mac limitations/checklist](macos.md). Native automated Mac
coverage is not physical microphone, Gatekeeper or notarization acceptance.
The installed runtime never saves audio; private guided collection is a separate
explicitly consented developer tool and must never enter Git or CI artifacts.

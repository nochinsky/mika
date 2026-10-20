# Architecture and safety

Mika is a one-shot English dictation CLI for Mac, Linux and Windows:
**run → speak → Enter → one transcript on stdout → exit**. There is no daemon,
automatic agent submission, clipboard action or saved-audio runtime mode.
[Mac support](macos.md) is experimental; public availability and a reported
physical-device smoke test do not imply full acceptance or notarization.

## Runtime pipeline

1. `main.c` validates arguments and acquires the controlling terminal. `model.c`
   locates the fixed Granite model, asks before its first download and verifies
   its full size/SHA-256 on every dictation launch. Consent is not read from piped
   stdin. Help/version do not initialize microphones or ML engines.
2. `engine.c` initializes the pinned CPU backend, verifies/loads bundled Silero VAD
   and creates the ASR session. Missing/damaged VAD data fails closed. Both sessions
   use the CPU; VAD uses one thread, threshold 0.5 and no minimum speech duration.
3. `audio.c`/`pcm.c` capture mono 16 kHz float PCM from the default input into a
   bounded five-minute buffer. Enter finishes, Esc/Ctrl+C cancels. Pauses do not stop it.
4. Silero checks the **whole original recording**. No detected segments returns 3
   without ASR; malformed/failed admission returns 1. PCM is not trimmed,
   concatenated, rescaled or replaced.
5. Granite transcribes admitted audio. Empty recognition returns 3. `--raw` skips
   formatting, never admission. Failure/cancellation does not publish partial text.
6. Default mode releases speech/capture resources, then loads FullStop. Guards
   preserve recognized words/order and obvious literals. A bounded negation-break
   guard rejects certain hazardous sentence splits, not every meaning change.
   Ordinary formatting failures keep raw text with a warning. Loader diagnostics
   identify a library/export and native error, not inference exception contents.
7. Cleanup frees sessions before borrowed models, restores the terminal and exits.
   Synchronous third-party work can delay cancellation. Audio remains in memory.

## Module boundaries

| Module | Responsibility | Boundary |
| --- | --- | --- |
| `main.c` | Control flow, cancellation and output | No automatic execution |
| `platform.c` | Terminal, signals, UTF-8 files, locks/time | Native Windows/POSIX |
| `audio.c`, `pcm.c` | Capture and bounded PCM ownership | No file recording |
| `verify.c` | Complete size/SHA-256 checks | Crypto/platform, no network |
| `model.c` | Consented download and verified atomic publication | Curl stays here |
| `assets.cpp` | Executable-relative bundled paths | Reject rooted/traversing suffixes |
| `engine.c` | CPU speech admission and ASR lifecycle | Pinned transcribe API |
| `punctuation*`, `fullstop*` | Formatting guards and native runtime bridge | CPU provider, raw fallback |

The asset locator and verifier are shared, not configurable registries. Libraries
are loaded from the executable's sibling payload rather than the working directory.
Diagnostics are caller-owned and bounded; they escape controls/non-ASCII bytes and
may contain OS filesystem paths. They do not include dictated text, generic C++
exception messages or persistent diagnostic state. Only callers print them to stderr.

## Speech admission is not confidence

The ASR previously returned nonempty text for silence, white noise and a steady
tone. Blank-output checks were therefore insufficient. Regression tests now reject
nine deterministic synthetic non-speech inputs and retain five public speech variants,
including quiet and brief speech with pauses.

This does not guarantee rejection of every noise/music input or the wrong speaker.
Quiet speech can be missed; admitted speech can be misheard, including lost negations.
The operating point remains provisional: do not tune it to one speaker/public file,
or substitute phrase blacklists, energy thresholds or nonempty output for validation.

## Recognition and formatting limits

The pinned Granite5CTC decoder uses greedy CTC collapse. It does not advertise
vocabulary/context-prompt, ITN or beam-search controls. Generic unsupported fields
are ignored with an upstream warning; they do not provide technical-word biasing.
Versions, identifiers and names can be wrong before formatting. FullStop preserves
source tokens; it is not a spelling repair or version parser.

Clipped input loses information before decoding. Attenuating an already saturated
recording cannot recover it. The explicit developer recorder warns about substantial
PCM saturation but changes neither audio nor OS levels. Neither that warning nor
public-file inference establishes natural-dictation accuracy.

Review important names, numbers, negations and constraints. Exit 0 is not a
confidence score or permission for unattended execution.

## Validation boundaries

- **Model-free:** actual owned core/CLI with fake ML, checksums and paths, guards,
  local HTTPS, installer/package transactions and sanitizers. No ML fetch or capture.
- **Native:** real backend/formatter, public speech, five-minute processing,
  admission/integrity failures and installed/relocated execution on all platforms.
- **Hardware:** separately consented microphone capture, permissions, trust,
  natural speech and live timings. Hosted CI does not establish these.

See [validation methods](validation.md), [dated Linux measurements](laptop-validation.md)
and [Mac acceptance](macos.md#validation-status). Private developer recordings must
never enter Git, CI, release assets or delegated review.

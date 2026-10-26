# Continuous-session experiment

Status: **offline prototype, not an installed-app feature**. The normal Mika
command and five-minute limit are unchanged. There is no microphone entry point
here. This experiment tests whether bounded audio chunks can support a future
session that stays open until Enter, including long pauses.

The processing component is C17 (`segmenter.c`). Python is a developer-only
evaluation driver for that compiled component and the existing native speech
libraries; it performs no Python ML inference. No audio/model is downloaded or
uploaded, and no microphone is opened. Generated WAVs and reports belong in an
ignored build directory, outside Git and release packages.

## Current design

- One fixed-size PCM buffer. Chunk size has a bound; session duration has no timer.
- Pause cuts are considered after a minimum chunk length. A forced maximum bounds
  memory when someone speaks without a suitable pause. Silence does not end the session.
- Every original sample is retained once, in order. No trimming, overlap,
  rescaling, transcript de-duplication, spelling repair or guessed corrections.
- Ready audio is borrowed and cannot be overwritten until consumed. The caller
  must retry unconsumed input. The unit test exercises this backpressure contract.
- The evaluator verifies the pinned Granite and Silero weights, uses streaming
  Silero probabilities to select boundaries, and a separate mandatory offline
  Silero admission pass before each chunk's ASR, matching the app's gate settings.
- One CPU recognition session is reused sequentially. This is application-level
  chunking of an offline model, **not native Granite streaming**.
- A final chunk shorter than 0.1 seconds is preserved and zero-padded only for the
  recognizer's minimum input length. That padding is reported explicitly.

The C component is single-worker code, not a real-time audio callback. Live
capture needs a separate bounded producer queue; a slow consumer must fail
explicitly rather than discard PCM or grow the queue indefinitely. That queue,
keyboard cancellation, no-output-on-cancel handling and microphone integration
are not implemented here. The offline evaluator pauses its file reader during
inference and therefore cannot prove live capture continuity.

Transcript text is accumulated until the end and grows with the amount spoken.
Only recording storage is fixed-size. The experiment does not evaluate the
formatter or solve its 32,768-byte input limit, sentence boundaries or negation
scope across chunks. See [measured findings](RESULTS.md) before using any result
to justify changing the production app.

## Build and test the native component

No ML assets or external libraries are needed for these tests:

```sh
cmake -S experiments/continuous -B build-continuous -DCMAKE_BUILD_TYPE=Release
cmake --build build-continuous --config Release --parallel 2
ctest --test-dir build-continuous -C Release --output-on-failure --no-tests=error
```

The unit test verifies every sample in a simulated 30-minute PCM session, along
with pause/forced/end boundaries, invalid inputs, ready-buffer backpressure,
silent chunks and short tails. This is synthetic PCM integrity, not recognition.
The separate experiment workflow runs it on Windows, Linux and Mac, with
additional address/undefined-behavior sanitizer checks on Linux.

## Evaluate explicit audio files

Requires Python 3.12+ standard library and a trusted installed Mika 0.3.2 shared
speech backend. The driver was exercised on Windows. Linux shared-library loading
is provided but not locally accepted; Mac release bundles statically link the
speech backend and cannot be used by this driver. The C component is portable.

Obtain the upstream public `samples/jfk.wav` at the exact transcribe revision
pinned in the main CMake file. Its SHA-256 is checked by the fixture generator.
Create a **new** fixture directory with 40 copies for ten minutes or 120 copies
for thirty minutes (11 seconds of public speech plus four seconds of silence):

```sh
python experiments/continuous/make_public_fixture.py --sample /path/to/jfk.wav \
  --copies 120 --output-dir build-continuous-data/public-30min
```

Windows example; adjust paths to the compiled DLL and existing model:

```powershell
python experiments/continuous/evaluate.py `
  --segmenter build-continuous/Release/mika-segmenter.dll `
  --app "$env:LOCALAPPDATA/Mika/app" `
  --model "$env:LOCALAPPDATA/Mika/models/granite-speech-5.0-470m-turboctc-Q4_K_M.gguf" `
  --audio build-continuous-data/public-30min/audio.wav `
  --reference build-continuous-data/public-30min/reference.txt `
  --kind repeated-public --max-seconds 60 --min-seconds 10 --pause-ms 800 `
  --output build-continuous-data/public-30min/report.json
```

Reports compare concatenated PCM hashes/frame offsets and use the existing
strict WER scorer with the predeclared reference. Reports omit hypotheses unless
`--include-transcript` is explicitly supplied and never overwrite an existing
report. `--pause-ms 0` selects fixed boundaries. A sufficiently long maximum
provides a whole-file comparison for a short fixture. The evaluator's 300-second
per-chunk guard is not a session-duration bound.

The synthetic boundary fixture uses the frozen text in `synthetic-case.txt`,
Windows Microsoft David Desktop, rate 0, and System.Speech output at mono
16-bit/16 kHz. Label it `--kind synthetic-boundary`; never describe it as a human
dictation benchmark. Preserve its reference, including number spellings, and
compare hypotheses with whole-file recognition. Do not change references after
seeing predictions or hide the fact that numeral formatting affects strict WER.

## Before a live option

1. Evaluate varied, separately consented natural speech and forced cuts, especially
   numbers, negations, brief words, names and a sentence crossing a boundary.
2. Decide how to handle a maximum-length cut with no safe pause. Current fixed-cut
   errors are a release blocker, not a reason to insert hand-written corrections.
3. Add the bounded capture queue, slow-consumer/device failure and cancellation
   tests, then real microphone/keyboard acceptance on the target platforms.
4. Validate formatting and final stdout behavior on long sessions. Keep the
   experiment out of installers until these gates are satisfied.

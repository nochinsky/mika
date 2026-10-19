# Laptop and spoken-prompt validation

These are developer tools, not new Mika runtime features. Reports distinguish
software regressions, public-file resource costs, actual microphone startup and
natural spoken-prompt accuracy. None is a substitute for the others.

## Fast model-free checks

This separate CMake entry point shares Mika's actual core targets and warning/
sanitizer settings. It never fetches dependencies or prepares ML assets. It needs
CMake 3.24+, a C17/C++17 compiler, system libcurl 7.85+/OpenSSL Crypto 1.1.1+ and
Python 3.12+ **standard library only**. No installed Mika, microphone, speech model,
ONNX Runtime, SentencePiece or Python ML packages are needed.

```sh
cmake -S tests/model-free -B build-model-free -DCMAKE_BUILD_TYPE=Release
cmake --build build-model-free --parallel 4
ctest --test-dir build-model-free --output-on-failure
```

Coverage: PCM/checksum/platform tests, guard/renderer tests, actual main/platform
code with fake speech/audio, local HTTPS downloads, installer transactions,
packaging/metadata, evaluation math and benchmark-tool consent/privacy checks.
The CLI test's model-preparation path is real, but microphone/inference are fake.
It never accepts first-run download consent. Formatter model quality and actual
inference/module loading still require the full build and its existing tests.
Use a separate `build-model-free-asan` with `-DMIKA_SANITIZERS=ON` for ASan/UBSan.

## File-pipeline latency and memory

Build the normal application first as described in [CONTRIBUTING.md](../CONTRIBUTING.md).
An existing verified speech model can be reused without copying or redownloading.
For example on Linux:

```sh
model="$HOME/.local/share/mika/models/granite-speech-5.0-470m-turboctc-Q4_K_M.gguf"
python3 scripts/benchmark_durations.py --probe build/bin/mika-inference-test \
  --model "$model" --sample build/_deps/transcribe-src/samples/jfk.wav \
  --runs 5 --durations 10 60 300 --cache-modes warm evict \
  --output build/durations-report.json
```

This runs fresh raw/default processes on exact-length **repeated public audio**.
It checks formatting preservation, not intended-speech accuracy. Longer runs can
be CPU/memory intensive. No microphone is opened, private recording is read, or
transcript is retained in the report. The inference probe includes full model
checksum, decoding, loading, inference, formatting where enabled, and teardown.
It does **not** include terminal startup or microphone initialization. Reported
peak RSS is whole-process peak, not formatter-incremental memory.

`warm` means normal filesystem caches, not guaranteed prewarmed files. `evict`
requests Linux/POSIX file-local `POSIX_FADV_DONTNEED` for the probe, sample, speech
weights and formatter payload before each process. This is **best effort, not a
guaranteed cold start**: mapped/shared pages, filesystem metadata and other caches
can remain warm. It never writes global drop-caches settings, needs no sudo and
must not be compared as if it were a rebooted system. This mode is unavailable on
Windows. Metadata records CPU, governor, power-source status and load when available;
background workloads, thermal limits and power policy still affect comparisons.

The existing `benchmark_pipeline.py` also accepts `--runs` and `--cache-mode` for
one input. Default remains five fresh processes with normal filesystem caches.

## Actual launch-to-Listening (Linux only, opt-in microphone)

```sh
python3 scripts/benchmark_microphone.py --binary build/bin/mika \
  --allow-microphone --runs 5 --listen-seconds 1.2 \
  --output build/microphone-report.json
```

This explicitly opens the **default microphone**, observes the real CLI's first
Listening status through a private PTY, briefly captures into memory, and presses
Esc. It checks exit 130, no stdout, and restored terminal modes. It records the
launch/observed-listening/cancellation timings and whole-child peak RSS via `wait4`.
`audio_progress_observed` checks that the CLI's frame counter reached one second;
that proves sample delivery, not correct input selection or intelligible audio.
Audio is never saved/uploaded and no transcript is kept. At most 10 runs and 5
seconds of post-Listening capture per run are accepted; each process has a timeout.
The model must already be installed. A first-download prompt is declined.
Optional `--cache-mode evict --model "$model"` requests the same best-effort file
cache eviction; `--model` is **not** a CLI model-location override.

## Guided natural-prompt corpus (separate explicit save consent)

For the easiest local Linux session after building the probe and installing the
speech model, run:

```sh
python3 scripts/guided_validation.py --consent-save-audio
```

It checks prerequisites/default input, asks before recording, creates a private
Git-ignored session, offers playback/retakes for capture problems, then scores raw
and formatted recognition locally. It does not upload audio or retain hypotheses
in the report. `--probe PATH --model PATH` selects an explicit developer build and
verified speech file; `--cases negation numbers hesitation` makes a short pilot.
Keep a frozen probe/assets copy when comparing changes during a live session.
Record once, then rerun evaluation against that same corpus rather than rerecording
until recognition improves. The installed Mika command still never saves audio.

[`tests/spoken_prompt_cases.json`](../tests/spoken_prompt_cases.json) contains 12
predeclared prompts/references/checks: negations, constraints, numeric contrasts,
versions, technical literals, conditional actions and spoken corrections. It is
**not yet audio evidence**. Multiple accents/noise conditions require additional
consented sessions and metadata; one speaker on one microphone cannot establish
broad dictation accuracy. Do not synthesize speech and call it a human benchmark.

The recorder below deliberately differs from Mika's no-saved-audio contract: it is
an opt-in **developer collection tool** that saves private WAVs. It requires ffmpeg
with PulseAudio input support and an interactive Linux terminal. Do not run it
without the speaker's explicit consent. Use a new ignored `build-*` directory;
never put recordings/transcripts in git or upload them as CI artifacts.

```sh
python3 scripts/record_spoken.py --consent-save-audio \
  --output-dir build-private-dictation/session-01
# Optional: --review for playback/retakes, --cases negation numbers path;
# --seconds 20 is the maximum per prompt
```

Read each prompt naturally after starting it; Enter ends the clip, with an
automatic 20-second maximum (configurable up to 30). The manifest is fixed before
recording. Owner-only permissions are used for new files. Existing corpora are
never overwritten. Ctrl+C discards the unfinished clip and keeps accepted clips.
Listen for capture/truncation problems **before** running recognition. A stopped
session's manifest can include missing clips; evaluation rejects it explicitly.
Choose a new directory for another session. Delete private corpora when finished.

```sh
python3 scripts/evaluate_spoken.py --probe build/bin/mika-inference-test \
  --model "$model" --manifest build-private-dictation/session-01/manifest.json \
  --output build-private-dictation/session-01/report.json
```

The evaluator reads **only explicitly supplied paths**, runs raw and formatted
inference, reports word error rate (WER), formatting preservation/fallback, and
critical-phrase review flags. Case/punctuation-normalized WER is not sufficient
for identifiers: separate literal checks retain internal punctuation and can be
case-sensitive. Number-word/reference alternatives are predeclared, not added
after seeing output. Literal flags can expose an inherent ASR limitation (e.g.
spoken “underscore” not yielding `_`), not necessarily a formatter regression.
Critical checks are conservative exact-phrase checks, **not a semantic judge**.
Review meaningful errors manually, including punctuation that changes intent.

Reports omit transcripts by default. `--include-transcripts` explicitly saves
reference/hypothesis text and must only be used in a private ignored location.
Reports still contain case IDs, audio hashes and system metadata; treat them as
private unless reviewed. Pipeline failures are reported separately, not silently
scored as successful empty transcripts. WER is micro-averaged over scored cases,
and can exceed 100% with insertions. Missing cases/failures must accompany scores.

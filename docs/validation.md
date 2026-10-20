# Testing and measurement

Software regressions, public-file performance, microphone behavior and natural
recognition accuracy are separate kinds of evidence. Report which was measured.
Developer tools below do not add recording or configuration features to Mika.

## Fast model-free checks

Requires CMake 3.24+, C17/C++17, system libcurl 7.85+/OpenSSL Crypto 1.1.1+ and
Python 3.12+ standard library. No ML packages, downloaded weights, installed Mika
or microphone are needed.

```sh
cmake -S tests/model-free -B build-model-free -DCMAKE_BUILD_TYPE=Release
cmake --build build-model-free --parallel 4
ctest --test-dir build-model-free --output-on-failure
```

This shares the actual core targets and tests PCM, hashes/paths, engine policy
with fake ML, cleanup/cancellation, original PCM preservation, CLI fixtures,
formatting guards/diagnostic escaping, local HTTPS, installer/package transactions
and evaluation tools. It does not exercise real inference or desktop permissions.
For ASan/UBSan, use a separate build with `-DMIKA_SANITIZERS=ON` and
`ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`. Third-party code is not
itself instrumented.

## Native and public-file tests

Build normally using [CONTRIBUTING.md](../CONTRIBUTING.md). Set `MIKA_TEST_MODEL`
to an existing verified Granite file to include raw/formatted speech, five-minute
processing and real admission checks:

```sh
cmake -S . -B build -DMIKA_TEST_MODEL=/absolute/path/to/model.gguf
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
```

Windows multi-config builds need `--config Release` and CTest `-C Release`.
Tests do not open a microphone. Native CI also checks actual installed/relocated
packages on Mac, Linux and Windows. [Mac hardware acceptance](macos.md#validation-status)
is separate.

The `speech-admission` test rejects nine deterministic synthetic silence/noise/tone
inputs, admits five public speech variants and fails closed on missing, truncated
or wrong-hash VAD data in raw/default modes. Damage is confined to temporary
relocated payloads. Admission does not prove intelligibility or intended speaker;
quiet admitted speech can still lose negations.

## File latency and memory

Example using an existing Linux model cache:

```sh
model="$HOME/.local/share/mika/models/granite-speech-5.0-470m-turboctc-Q4_K_M.gguf"
python3 scripts/benchmark_durations.py --probe build/bin/mika-inference-test \
  --model "$model" --sample build/_deps/transcribe-src/samples/jfk.wav \
  --runs 5 --durations 10 60 300 --cache-modes warm evict \
  --output build/durations-report.json
```

Fresh raw/default processes receive exact-length **repeated public audio**. Timing
includes checksum, decoding, model loading, admission, ASR, optional formatting and
teardown—not terminal startup, microphone opening or live Enter-to-output. Peak RSS
is whole-process, not incremental formatter memory. No private recordings are read
or hypotheses retained in reports. Long runs can consume substantial resources.

`warm` means ordinary filesystem caches, not guaranteed prewarming. POSIX `evict`
requests file-local `POSIX_FADV_DONTNEED`; shared/mapped pages and metadata can remain
cached. It is best effort, not a rebooted/cold-system comparison. It needs no sudo,
never changes global cache settings and is unavailable on Windows. Power policy,
thermals, background load and run order still matter.

The probe emits `speech_gate_ms`, `asr_ms` and `speech_admitted` on stderr. Rejected
input avoids ASR compute but still pays verification/initialization costs.
`benchmark_pipeline.py` measures one input and also accepts `--runs`/`--cache-mode`.
Formatter-only evaluation and measurements are in [the formatting guide](punctuation.md#build-and-measurement).
[Dated results](laptop-validation.md) include their hardware and measurement scope.

## Microphone startup — Linux, explicit opt-in

```sh
python3 scripts/benchmark_microphone.py --binary build/bin/mika \
  --allow-microphone --runs 5 --listen-seconds 1.2 \
  --output build/microphone-report.json
```

This opens the default input, observes Listening/frame progress through a private
PTY, then sends Esc. It checks exit 130, empty stdout and restored terminal modes;
records launch/listening/cancellation timing and child peak RSS via `wait4`; and
never saves audio or transcripts. Frame delivery is not proof of intelligibility.

The model must already exist; first-download consent is declined. Limits are ten
runs and five seconds post-Listening per run, with process timeouts. Optional
`--cache-mode evict --model "$model"` requests file-local cache eviction; this is
not a runtime model override.

## Natural dictation — separate saved-audio consent

The guided collector is a **Linux-only developer tool** requiring ffmpeg with
PulseAudio support, a built inference probe and an existing verified model:

```sh
python3 scripts/guided_validation.py --consent-save-audio
```

It checks prerequisites/default input, asks before capture, creates an ignored
private session, offers playback/retakes, then evaluates locally. `--probe PATH
--model PATH` selects the comparison build and verified model; `--cases negation
numbers hesitation` selects a pilot. Keep a frozen probe/assets copy to compare
builds on the same recordings rather than rerecording until a result improves.

The [12 predeclared prompts](../tests/spoken_prompt_cases.json) cover negations,
constraints, numbers, versions, literals, conditions and corrections. Prompt text
alone is not audio evidence. One speaker/input cannot establish accuracy across
accents, noise or hardware. Do not label synthesized speech a human benchmark.

For direct collection and evaluation:

```sh
python3 scripts/record_spoken.py --consent-save-audio \
  --output-dir build-private-dictation/session-01
python3 scripts/evaluate_spoken.py --probe build/bin/mika-inference-test \
  --model "$model" --manifest build-private-dictation/session-01/manifest.json \
  --output build-private-dictation/session-01/report.json
```

Unlike installed Mika, this collector **saves private WAVs**. Obtain explicit
speaker consent first. New files use owner-only permissions; existing corpora are
never overwritten. Enter ends a take, with a default 20-second maximum; Ctrl+C
discards the unfinished take. Optional `--review` offers playback/retakes.

Listen for capture problems before recognition. A warning at 1% exact-limit PCM
samples indicates possible clipping, not recognition accuracy. Neither waveform
nor OS settings are changed. Lowering an already clipped file cannot restore it.
Incomplete manifests fail evaluation rather than silently omitting cases.

The evaluator reports micro-averaged WER, preservation/fallback, failures and
critical-phrase flags. WER can exceed 100% through insertions. Literal checks retain
internal punctuation/case; critical checks are exact-phrase flags, not semantic
judgments. Number/reference alternatives must be predeclared, not added after
seeing hypotheses. Review meaning-changing errors separately.

Reports omit transcripts by default. `--include-transcripts` explicitly saves them;
case IDs, audio hashes and system metadata remain private even without hypotheses.
Never commit/upload recordings, transcripts or private reports to Git, CI, releases
or delegated review. Retain/delete recordings according to the speaker's consent;
never remove an existing corpus merely to clean a build directory.

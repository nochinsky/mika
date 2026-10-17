# Experimental punctuation — not released

**Keep raw transcription as the default.** This prototype is not in the public
installer, does not change Granite, and is not approved for a release. Ordinary
builds do not fetch or load its dependencies. Release-bundle builds and the
release packager explicitly reject the experimental configuration.

The first candidate is the English-only **Edge-Punct-Casing INT8** model,
packaged by sherpa-onnx. It tags existing words with capitalization and optional
commas, periods, and question marks. It does not generate replacement wording,
correct speech-recognition errors, or support exclamation marks.

## Try a source build

Use the development dependencies in [CONTRIBUTING.md](../CONTRIBUTING.md), plus
Python 3.8+ for the **build-time asset fetcher only**. Explicitly enabling this
option downloads pinned model, vocabulary, C API header, CPU runtime, and notices;
the installed program does not need Python. No text/audio is uploaded.

```sh
cmake -S . -B build-punctuation -DMIKA_EXPERIMENTAL_PUNCTUATION=ON -DMIKA_NATIVE_CPU=ON
cmake --build build-punctuation --config Release --parallel 8
./build-punctuation/bin/mika --punctuate
```

On Windows with Visual Studio, the command is typically
`.\build-punctuation\bin\Release\mika.exe --punctuate`.
Do not enable `MIKA_RELEASE_BUNDLE` in this prototype build. Native CPU tuning
makes this a local test binary, not a portable binary for other computers. The
conservative scalar source-build path can be much slower than Mika's dispatched
release build; CI tunes the non-distributed prototype to its runner CPU rather
than weakening the five-minute test.

- `mika` still produces raw output, including in an experimental build.
- `mika --punctuate` explicitly opts into the formatting pass for that invocation.
- Enter, Esc/Ctrl+C, the five-minute cap, stdout redirection, and the quiet UI
  remain unchanged. Formatting is a transient stderr status.
- The existing consented 279 MB speech-model download is unchanged. Punctuation
  assets are installed with this **opt-in source build**, not downloaded during
  dictation. Keep the `punctuation/` directory beside the experimental executable.
- This prototype supports native x86-64 Linux and Windows, not ARM/macOS builds.

## Safety and fallback

After transcription, Mika copies the raw text and releases the speech engine and
recording buffer before loading punctuation. Both punctuation data files are
size/SHA-256 verified on use. Libraries load lazily from the executable's
`punctuation/` directory, never by searching the working directory.

The guard accepts only the same original tokens in the same order, allowing
ASCII case changes, whitespace normalization, and at most one trailing `,`, `.`,
or `?` per word. Original punctuation, apostrophes, hyphens, digits, and spelling
cannot be removed or replaced; duplicate punctuation is rejected. There is no
forced final period because an unfinished question should not be guessed into a
statement just to make output look complete.

Missing/corrupt assets, missing libraries/entry points, model failures, C++
exceptions, allocation failure, and rejected output keep the **original transcript**
with a stderr warning. A cancellation discards both versions and prints no text.
Synchronous native calls cannot poll Esc while executing; queued cancellation is
checked immediately afterward. Native crashes/abort/OS termination cannot be
recovered in-process—fallback is not a sandbox or a crash-recovery guarantee.

This backend is deliberately limited to ASCII input, 32,768 bytes total and
96 bytes per word. Unsupported text, including accented names, stays raw rather
than being passed through upstream's byte-wise casing. **Word preservation does
not guarantee preservation of meaning:** a misplaced comma or question mark can
still change how the same words are understood.

Native SDK code remains mapped until process exit, avoiding unsafe unload-time
registry/TLS teardown (and the resulting sanitizer-detected registry leaks).
The MSVC bridge disables the usual `extern "C"`-is-nothrow assumption so C++
exceptions from the SDK can reach its fallback boundary. This is not SEH/crash
recovery. Sessions and returned strings are freed normally. Mika still exits after one run;
there is no persistent service or cache in the background.

## Quality assessment

The authored 30-example regression corpus is
[`tests/punctuation_cases.json`](../tests/punctuation_cases.json). It includes
ordinary conversation, questions, work dictation, names/brands, and literals.
These are text fixtures, **not microphone recordings or a general accuracy
benchmark**. References reflect one writer's punctuation; valid alternatives can
score as mismatches.

Initial local results:

| Check | Result |
| --- | --- |
| Word preservation | All 30 examples retained every word |
| Formatting fallback | None on these fixtures |
| Punctuation F1 against references | 67.5% |
| Case-change F1 against references | 90.1% |
| Expected question marks recovered | 5 of 10 |
| Outputs with a final period/question mark | 8 of 30 |
| Exact reference matches | 6 of 30 |

The preliminary quality bar was set before running this corpus: no lost words or
ordinary-input fallback, punctuation/case-change F1 at least 90%, and question-mark
recall at least 90%. **The candidate does not pass.** Do not make it the default,
force punctuation heuristically, or tune this corpus merely to turn the gate green.
A successful engineering CI run means the prototype behaves safely, **not** that
its formatting quality is approved. The quality-report JSON records that decision
separately.

Examples of limitations include `Github` instead of `GitHub`, unchanged `openai`
and `javascript`, and `What time does the meeting start` without a question mark.
Proper mixed-case name restoration is unfinished in the upstream decoder.

## Resource measurements and checks

Reproduce the native, punctuation-only measurements and authored assessment:

```sh
ctest --test-dir build-punctuation -C Release --output-on-failure
python3 scripts/evaluate_punctuation.py \
  --probe build-punctuation/bin/mika-punctuation-test \
  --assets build-punctuation/bin/punctuation \
  --output build-punctuation/quality-report.json
python3 scripts/benchmark_punctuation.py \
  --probe build-punctuation/bin/mika-punctuation-test \
  --assets build-punctuation/bin/punctuation \
  --output build-punctuation/resource-report.json
```

Use `python` and the `bin/Release/*.exe` paths on Windows as appropriate.
The benchmark uses five fresh processes per input, normal filesystem caches,
and reports checksum/loading/inference/teardown time plus whole-process peak RSS.
It is **not incremental memory inside Mika**, an end-to-end dictation benchmark,
or a prediction for another CPU.

On the i7-13700K/WSL development machine, the integrated native formatting probe
measured approximately **40 ms / 52 MiB** for 18 words and **68 ms / 67 MiB** for
748 words (median stage time / whole-process peak RSS). The longer input is
repeated public speech text, not a natural five-minute dictation sample. These
numbers include integrity checks and the prototype's actual lazy-loading path;
they supersede the earlier bare-C-API probe's smaller process-RAM figures.

Native CI also measured the complete formatting stage (five fresh processes):

| Host | 18 words: time / process peak | 748 words: time / process peak |
| --- | --- | --- |
| Ubuntu 22.04 CI | 61 ms / 45 MiB | 100 ms / 61 MiB |
| Windows Server 2022 CI | 101 ms / 39 MiB | 145 ms / 55 MiB |

These are different machines/OS memory-accounting systems, not an OS performance
comparison. Windows uses peak working set. Payloads including notices measured
38,766,412 bytes on Linux and 29,267,539 bytes on Windows.

The model and vocabulary occupy 7,639,930 bytes combined. The untrimmed Linux CPU
runtime and C API libraries add 30,652,665 bytes: **38.3 MB uncompressed before
notices**. Smaller custom runtimes might reduce this, but no savings are assumed.

ONNX inference is configured with one thread. **The upstream tokenizer also
creates an idle hardware-sized thread pool:** the 24-logical-CPU development
machine reaches 25 OS threads during formatting. It would be misleading to call
this a single-OS-thread implementation. This unnecessary pool is another item to
fix before considering production integration.

Tests cover mutation/length/control-byte guards, missing and tampered assets,
unsafe native output, C++ exceptions, native cancellation, raw default/fallback,
quiet redirected output, terminal restoration, Unicode/relocated paths, and
native Windows classic-console behavior. With `MIKA_TEST_MODEL`, public JFK audio
is tested through real ASR then formatting, including the complete 300-second
repetition fixture. That confirms length handling and word retention, not natural
long-form accuracy. No test records a microphone.

Native CI can be requested with workflow **Build and test**, input
`punctuation=true`. It builds/tests ordinary releases first, then the opt-in
prototype on Ubuntu 22.04 and Windows Server 2022, and uploads **reports only** for
the prototype. It never publishes a punctuation release or prototype binary.

[Native validation run 39029275935](https://github.com/nochinsky/mika/actions/runs/39029275935)
passed eight ordinary-build suites plus ten opt-in prototype suites **on each
platform**, including real public-speech formatting, full five-minute input,
asset/exception fallback, relocated Unicode paths, and Windows console cancellation.
Both platforms reproduced the same failed quality gate; engineering success did
not promote the candidate to default. Local ASan/UBSan also passed all seven
configured suites, including the real native formatter and failure-injection
paths, without sanitizer suppressions. Third-party libraries themselves are not
instrumented by Mika's sanitizer option.

The first native attempt exposed scalar-build timeouts, not a punctuation failure;
its duration tests were retained unchanged and passed after runner-local CPU
tuning. No live microphone or natural five-minute dictation was used in these
checks. The public installer/release remains v0.1.2 and main is unchanged.

## Provenance and licensing

Exact sizes, hashes, URLs, and revisions are in
[`scripts/fetch_punctuation.py`](../scripts/fetch_punctuation.py). The mirror's
model/vocabulary hashes are verified; the original author's model card and source
license are Apache-2.0. sherpa-onnx v1.13.8 supplies the CPU-only, **no-TTS** shared
SDK, with static CRT on Windows; its ONNX Runtime is 1.28.2. Windows import-table
inspection found OS DLL imports, not a new Visual C++ redistributable dependency.

The build retains direct and no-TTS dependency license documents, including
ONNX Runtime third-party notices, Apache components, BSD FFT/clustering code,
Darts and thread-pool attribution headers, and Eigen's MPL-2.0 terms. No upstream
library/model is modified. Their source locations are recorded in the fetcher;
Eigen source is available at
<https://gitlab.com/libeigen/eigen/-/tree/5.0.1> (MPL source availability).
Redistribution must retain the actual linked components' notices and satisfy
applicable source-availability requirements. The prototype is deliberately
excluded from Mika's release packaging pending a production review.

Sources: [original model](https://huggingface.co/frankyoujian/Edge-Punct-Casing),
[paper](https://arxiv.org/abs/2407.13142),
[Sherpa model documentation](https://k2-fsa.github.io/sherpa/onnx/punctuation/pretrained_models.html),
[upstream decoder](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/sherpa-onnx/csrc/online-punctuation-cnn-bilstm-impl.h).

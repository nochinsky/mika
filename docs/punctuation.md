# Offline punctuation and case

`mika` uses English FullStop INT8 after Granite transcription. `mika --raw` skips
formatting entirely, including its data checks and runtime loading. There is one
fixed pipeline, no experimental build switch or model selector.

This is polish for quick agent prompts, **not an editor or a semantic guarantee**.
ASR can mishear words; formatting can choose misleading punctuation or casing.
Review important commands/messages. The model supports commas, periods and
question marks, not exclamation marks. No dictionary, spelling cleanup, forced
final period, LLM or cloud fallback is used.

## Safety contract

The native renderer projects predictions onto **original source character offsets**,
not reconstructed model words. Unknown pieces keep their original characters,
fixing the reference decoder's `<unk>`/hyphen problem. Unalignable normalization
keeps original case. Marks may be added only at complete original-word boundaries;
internal acronym periods and unsupported pre-punctuation are not emitted.

An independent C guard accepts only the same words/order, ordinary ASCII case
changes, normalized whitespace and at most one appended comma/period/question mark.
Original punctuation, spelling, digits, apostrophes and hyphens remain intact.
Obvious literals retain exact source case: numeric tokens, paths, emails,
underscored identifiers, code markers, internal dots/colons, leading-hyphen flags,
existing camelCase/PascalCase and uppercase acronyms. This is conservative: raw
`c++` stays `c++`, not `C++`. It is not a guarantee that every bare code identifier
will be recognized or that copied output is executable code.

A second, narrow rejection guard also refuses a **new internal period or question
mark immediately after a negation or its next word** (for example, splitting
“not execute cleanup” after “execute”). It covers `not`, `no`, `never`, `without`,
`cannot` and ASCII `n't` contractions. The whole candidate is discarded and the
original raw text is used with a warning; no replacement punctuation is invented.
Existing sentence boundaries and final punctuation remain allowed. This can
conservatively reject a valid sentence break. It does **not** parse scope beyond
one following word, repair a missing negation, or guarantee preserved meaning.

Supported text is ASCII, at most **32,768 bytes / 96 bytes per word**. Unsupported
text stays raw rather than risking character damage. Sequential **254-subword
windows / 16 overlap** keep attention memory bounded; source indices retain every
word through seams. CPU inference uses one configured intra-op/inter-op thread.
The native SentencePiece encoder avoids the earlier Sherpa idle tokenizer pool.

Mika copies raw text and releases speech/recording resources before loading the
formatter. Data files are size/SHA-256 verified on use, and libraries are loaded
from the executable's sibling `punctuation/` directory, not the working directory.
Data/runtime/inference/allocation/unsafe-output failures keep raw text with a
non-sensitive stderr reason. Cancellation discards both versions and prints
nothing. Queued cancellation is checked between stages/windows and after
synchronous calls. Native crashes/abort/OS termination cannot be recovered by an
in-process fallback; this is not a sandbox. Modules stay mapped until exit to
avoid registry/TLS teardown hazards; sessions, tensors and text are freed normally.

## Quality evidence and release policy

The original [30 references](../tests/punctuation_cases.json) remain unchanged.
The negation-boundary safeguard reproduced the same metrics and zero fallbacks
on both public corpora; a separate authored negative-instruction regression tests
intentional raw fallback. These small corpora do not establish semantic safety:


| Metric | Original 30 | Additional 60 |
| --- | ---: | ---: |
| Words/order preserved | 30/30 | 60/60 |
| Raw fallback | 0 | 0 |
| Punctuation F1 | 80.4% | 90.0% |
| Case-change F1 | 89.7% | 92.0% |
| Expected question marks | 10/10 | 16/16 |
| Extra question marks | 0 | 0 |

The [additional set](../tests/punctuation_holdout.json) was authored before its
first run, SHA-256
`daa9645bdb832bd9f510efee09161e5a96888636b954154dfc3a709afa752350`.
Its first pass exposed literal-case problems; a generic safety fix followed.
It is therefore **development validation, not an independent blind holdout**.
Predeclared style alternatives are reported separately from primary references.
No gold answer was rewritten to improve these scores.

The original 90% punctuation/casing and question-recall research thresholds are
still reported as **legacy advisory targets**; the original set still misses them.
The explicit product decision is to accept imperfect prose for fast agent
prompting, not claim the model suddenly passed. Hard release requirements remain
word/literal preservation, cancellation/fallback safety, clean stdout/exit behavior,
portable package validation and acceptable resource costs. The new
[24 agent-prompt fixtures](../tests/prompt_cases.json) exercise negations, numbers,
constraints, paths and identifiers without inventing a preferred prose style.
These test preservation after ASR, not intended-speech accuracy or all meanings.

Known weaknesses include `WHO` versus `Who`, brand casing (`Openai`, `Powershell`),
comma splices, sentence boundaries and disfluency. Some reference losses are valid
style alternatives, others are real mistakes. Neither an authored score nor a
five-minute repeated sample establishes natural dictation accuracy. The owner has
reported successful live prototype use in WSL; native Windows formatter validation
is automated, not a new live-microphone claim.

## Build and distribution

Follow [CONTRIBUTING.md](../CONTRIBUTING.md). Preparation/distribution strategy is
unchanged from the prototype: pinned original FP32 weights are fetched at build
time and converted with the existing pinned Python tooling, then the verified
INT8 model, vocabulary, CPU runtime, source-built native module and notices are
placed in `bin/punctuation/` and included in release archives. No separate asset
host, model cache migration or new download manager was introduced.

The Granite ASR GGUF remains a separately consented first-run download. Formatting
and the small mandatory CPU VAD weights remain inside the app and are replaced
with application updates. The
executable needs **no Python**, and performs no conversion/download/upload during
formatting. Never distribute a `MIKA_NATIVE_CPU=ON` speech build to unrelated CPUs;
release bundles use runtime CPU dispatch.

## Measurements and reproducibility

```sh
python3 scripts/evaluate_punctuation.py --probe build/bin/mika-punctuation-test \
  --assets build/bin/punctuation --output build/quality-report.json
python3 scripts/evaluate_punctuation.py --probe build/bin/mika-punctuation-test \
  --assets build/bin/punctuation --corpus tests/punctuation_holdout.json \
  --output build/holdout-report.json
python3 scripts/benchmark_punctuation.py --probe build/bin/mika-punctuation-test \
  --assets build/bin/punctuation --output build/resource-report.json
```

Windows uses `python`, `bin/Release/*.exe`, and CTest `-C Release` as appropriate.
Five fresh native processes per input with normal filesystem caches. Formatting
stage includes integrity checks, loading, tokenization, inference, rendering and
teardown. Peak RSS/Windows peak working set is whole-process, not incremental RAM.

Local i7-13700K/WSL static-dependency release-dispatch build: **121 ms / 119 MiB**
for 18 words, **224 ms / 119 MiB** for 748 repeated-public-JFK words. Local payload
including notices was **81,976,867 bytes**; compiler versions change module size.
Weights/vocabulary alone are **53,471,412 bytes**, not the complete footprint.
Earlier prototype Windows CI measured a 72.5 MB payload and 265/514 ms for those
inputs; different hardware/OS accounting make that unsuitable as an OS comparison.

`scripts/benchmark_pipeline.py --probe ... --model ... --sample ... --output ...`
includes full Granite checksum verification, WAV decoding, speech load/admission/
inference, optional formatting and teardown. Local **pre-admission-gate** five-run
medians were **457 / 581 ms** raw
versus formatted on public JFK, with **323 MiB peak for both** in that probe.
Checksum plus speech-model load was **220 ms**. This is model-ready timing, not
microphone initialization or actual launch-to-Listening latency. Do not add
formatting-only RSS to ASR RSS or generalize this file probe to every workload.
Older pipeline reports excluded the speech checksum and are not directly comparable.

Native CI covers Linux/Windows and experimental Apple Silicon macOS, raw/default
installed and relocated inference, console controls, integrity/failure injection,
exact-limit text and 300-second public speech, then uploads quality/resource reports.
Earlier [native prototype run 39036249265](https://github.com/nochinsky/mika/actions/runs/39036249265)
reproduced the conversion hash and identical 90-example outputs on both platforms;
that historical run alone is not production-packaging approval.

A separate [Core Ultra 5 laptop validation](laptop-validation.md) reproduces these
quality scores and reports actual microphone startup plus 10/60/300-second file
pipeline latency/memory. It does not claim natural spoken-prompt accuracy.

Experimental Apple Silicon builds use the same weights and native CPU-only
formatter through pinned ARM64 `libonnxruntime.dylib`; see [macOS status](macos.md).
The upstream runtime may include unused Core ML provider code, but Mika selects
only the default CPU provider. No GPU/Core ML execution provider is appended.

## Provenance and licenses

Exact URLs/hashes: [fetcher](../scripts/fetch_punctuation.py). FullStop English
[revision b26fd1c40e88678859048898218ea4edcc24c84a](https://huggingface.co/1-800-BAD-CODE/punctuation_fullstop_truecase_english/tree/b26fd1c40e88678859048898218ea4edcc24c84a)
is author-declared Apache-2.0. The retained card/configuration, standard license and
[modification notice](../licenses/fullstop-NOTICE.txt) describe the derived INT8
weights and conversion. No retraining took place.

CPU ONNX Runtime **1.28.2** (MIT plus third-party notices) comes from pinned
sherpa-onnx **v1.13.8** no-TTS SDK binaries; no Sherpa inference library is deployed.
Runtime source: <https://github.com/microsoft/onnxruntime/tree/v1.28.2>.
SentencePiece **v0.2.1**, commit
[31646a467d2051eb904e0b45de3a73e91fe1c1e3](https://github.com/google/sentencepiece/tree/31646a467d2051eb904e0b45de3a73e91fe1c1e3),
is statically built, unmodified, with internal dependencies; preserve Apache-2.0
and protobuf-lite/Abseil/Darts notices. It avoids a newer upstream build's automatic
Abseil checkout. Preserve actual component notices/source-availability obligations.

Mika's renderer/bridge is original MIT code, informed by
[Apache-2.0 reference tagging conventions](https://github.com/1-800-BAD-CODE/punctuators/tree/e0723a4f5dfe5f4fac8571a916ea03571b87edd3).

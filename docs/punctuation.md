# Experimental FullStop formatting — not released

**Raw transcription remains the default.** This branch replaces the earlier Edge
experiment with an English FullStop INT8 classifier. Granite is unchanged. The
public installer still provides v0.1.2 without formatting; this experiment is not
merged to main, a release, or an approved default. Release-bundle builds and the
release packager reject the experimental configuration.

## Try a developer build

Use the ordinary dependencies in [CONTRIBUTING.md](../CONTRIBUTING.md), plus
**Python 3.12+ for build-time conversion only**. Create a development environment:

```sh
python3 -m venv build-punctuation-tools
build-punctuation-tools/bin/python -m pip install -r scripts/requirements-punctuation.txt
cmake -S . -B build-punctuation -DMIKA_EXPERIMENTAL_PUNCTUATION=ON -DMIKA_NATIVE_CPU=ON \
  -DPython3_EXECUTABLE="$PWD/build-punctuation-tools/bin/python"
cmake --build build-punctuation --parallel 8
./build-punctuation/bin/mika --punctuate
```

On Windows, use `py -3.12 -m venv build-punctuation-tools`, install requirements
with `build-punctuation-tools\Scripts\python.exe`, and set `Python3_EXECUTABLE` to
that interpreter's absolute path. Use Visual Studio/vcpkg as described in
CONTRIBUTING, `cmake --build build-punctuation --config Release`, then
`.\build-punctuation\bin\Release\mika.exe --punctuate`. Activation and a global
execution-policy change are not required.

Explicitly enabling this build downloads the **210 MB original model**, converts
it locally using pinned developer packages, and verifies the resulting INT8 file's
exact size/SHA-256. It also fetches pinned tokenizer source and CPU runtime assets.
These are build-time network transfers, not dictation-time behavior. Cached,
verified converted weights skip conversion. No Python packages are embedded or
needed by the executable, and no model conversion or downloads occur in use.

- `mika` stays raw, including in experimental builds.
- `mika --punctuate` opts into formatting for that invocation only.
- Keep the sibling `punctuation/` directory with the executable.
- Enter, Esc/Ctrl+C, the five-minute cap, clean stdout/redirection and transient
  stderr UI are unchanged. No accounts, GPU, uploads, clipboard or daemon.
- Native-CPU builds are for the build machine, **not portable distributions**.
- This prototype targets x86-64 Linux and Windows, not ARM/macOS.

## Word safety and native implementation

After transcription, Mika copies the raw text and releases the speech engine and
recording buffer before formatting. It verifies both formatting data files on
use, then loads CPU ONNX Runtime and the source-built `mika-fullstop` module from
the executable's `punctuation/` directory, not the working directory.

The classifier predicts punctuation and per-character case. **The renderer copies
original source characters, never reconstructed model words.** SentencePiece
source offsets map case predictions back to the original text. Unknown pieces
(such as hyphens) are retained rather than rendered as `<unk>`. Unalignable
normalizer spans keep their original case. Punctuation predictions may be applied
only at complete original-word boundaries, not inside words. Acronym-internal
periods and unsupported pre-punctuation are not emitted.

An independent C guard accepts only the same words/order, ASCII case changes
outside protected literals, normalized whitespace, and at most one appended
comma/period/question mark. Original spelling, apostrophes, hyphens, digits and
punctuation cannot be deleted or replaced; existing terminal punctuation is not
stacked. No dictionary, forced-final-period rule, or spelling cleanup is used.
The model does **not support exclamation marks**.

**Obvious literals also retain their exact original case:** tokens containing
digits, internal dots/colons, path separators, underscores, email/code markers
(`/ \\ _ @ + # = < > [ ] { } $ % & | ^ ~` or backticks), or a leading hyphen.
Ordinary trailing sentence punctuation is ignored for that classification;
English apostrophes and internal hyphens remain normal words. This is conservative:
raw `c++` remains `c++`, rather than being normalized to `C++`. It is not a promise
that an entire transcript is safe executable code or that all proper names will
be capitalized correctly.

The supported envelope remains ASCII, 32,768 input bytes and 96 bytes per word.
Unsupported input stays raw. Sequential **254-subword windows with 16-subword
overlap** bound model attention memory; overlap is trimmed symmetrically with
source indices retained. No words are truncated at window boundaries. CPU
inference uses one configured intra-op/inter-op thread and native SentencePiece;
the old Sherpa tokenizer's unused hardware-sized pool is no longer involved.

Missing/corrupt data, missing libraries/symbols, allocation/model/shape/type errors,
C++ exceptions or rejected results preserve the original transcript with a stderr
warning. Cancellation discards both versions and prints no transcript. Queued
cancellation is checked between stages/windows and after synchronous native calls.
Native crashes, aborts and OS termination are not recoverable in-process: this is
not a sandbox. Modules remain mapped until exit to avoid registry/TLS teardown
hazards; sessions, temporary tensors and text are freed normally.

## Quality: improved, still not an approved default

The original [30 examples](../tests/punctuation_cases.json) and their original
thresholds/references are unchanged. The separate
[60-example development validation set](../tests/punctuation_holdout.json) was
written before its first model run (SHA-256
`daa9645bdb832bd9f510efee09161e5a96888636b954154dfc3a709afa752350`). It includes
questions, indirect questions/commands, contractions, brands, literals, ambiguity,
fragments and disfluency. Predeclared acceptable style alternatives are reported
separately and **do not replace the primary-reference quality-gate score**.

Local results for the current source-preserving prototype:

| Check | Original 30 | Additional 60 |
| --- | ---: | ---: |
| Words/order preserved | 30/30 | 60/60 |
| Raw fallback | 0 | 0 |
| Punctuation F1 | 80.4% | 90.0% |
| Case-change F1 | 89.7% | 92.0% |
| Expected question marks | 10/10 | 16/16 |
| Extra question marks | 0 | 0 |
| Outputs with final period/question mark | 30/30 | 60/60 |
| Exact primary references | 14/30 | 42/60 |
| Primary or predeclared acceptable reference | 14/30 | 48/60 |

The earlier Edge prototype scored 67.5% punctuation F1, recovered 5/10 question
marks and supplied a final mark in only 8/30 examples. FullStop is a substantial
improvement on these fixtures, **not evidence of general dictation accuracy**.

The first pass on the additional 60 scored 90.0% punctuation / 89.5% casing and
revealed unwanted case changes in paths/emails. The generic literal-safety fix
above was made after that observation. Consequently this set is now development
validation, **not a still-independent blind holdout**. No expected answer was
changed; the first-pass report remains in local build artifacts. References that
expect `C++` from raw `c++` count against the conservative literal policy.

The original gate requires no word loss/ordinary-input fallback, punctuation and
case-change F1 >=90%, and question recall >=90%. **The original set still fails.**
Passing the additional set cannot override that or approve a default/release.
Neither passing engineering CI nor a tiny authored corpus replaces representative
natural dictation and user assessment.

Real remaining problems include `WHO` instead of interrogative `Who`,
`State-of-The-art`, incomplete brand casing (`Openai`, `Powershell`), comma splices,
and difficulty with disfluency. Word preservation cannot guarantee preservation
of meaning. Text-only formatting cannot recover every intended pause or tone.
Some score losses are harmless style choices (Oxford commas, `I am fine, thank
you.` versus two sentences); report these limitations rather than tuning the
corpus/adding heuristics just to turn a gate green.

## Measurements and reproducibility

```sh
ctest --test-dir build-punctuation --output-on-failure
python3 scripts/evaluate_punctuation.py --probe build-punctuation/bin/mika-punctuation-test \
  --assets build-punctuation/bin/punctuation --output build-punctuation/quality-report.json
python3 scripts/evaluate_punctuation.py --probe build-punctuation/bin/mika-punctuation-test \
  --assets build-punctuation/bin/punctuation --corpus tests/punctuation_holdout.json \
  --output build-punctuation/holdout-report.json
python3 scripts/benchmark_punctuation.py --probe build-punctuation/bin/mika-punctuation-test \
  --assets build-punctuation/bin/punctuation --output build-punctuation/resource-report.json
```

Use `python`, `-C Release` and `bin/Release/*.exe` as appropriate on Windows.
Five fresh native processes per text input, normal filesystem caches, include
integrity verification, lazy loading, tokenization, inference, rendering and
teardown. Python only drives the tests. Whole-probe peak RSS/Windows peak working
set is **not incremental Mika RAM**, cold-disk timing or an OS comparison.

Measured complete formatting stage (median time / whole-process peak):

| Host | 18 words | 748 words |
| --- | --- | --- |
| Local i7-13700K / WSL | 119 ms / 124 MiB | 219 ms / 124 MiB |
| Ubuntu 22.04 native CI | 203 ms / 119 MiB | 340 ms / 119 MiB |
| Windows Server 2022 native CI | 265 ms / 116 MiB | 514 ms / 116 MiB |

These are different machines and memory-accounting systems, **not an OS speed
comparison**. The long input repeats public JFK text, not natural five-minute
dictation. The earlier standalone ONNX-only 217 ms measurement excluded
verification/tokenization/rendering and is not the complete formatter. A separate
local exact-limit run (32,768 bytes) observed a peak of one OS thread; this is not
an unmeasured Windows thread-count claim.

Complete payloads including notices measured **81,941,307 bytes on Linux CI** and
**72,489,378 bytes on Windows CI** (about 82 MB / 72.5 MB decimal). Compiler/build
versions slightly change the native module size. Weights/vocabulary alone are
**53,471,412 bytes**, not the whole download/runtime. A native tokenizer/bridge is
built from source; unused Sherpa/C++ API libraries, Python packages, original FP32
weights and import libraries are not deployed.

`scripts/benchmark_pipeline.py` additionally compares five raw/formatted fresh
public-WAV inference probes, using `--probe`, `--model`, `--sample`, and `--output`.
It includes WAV decoding, speech load/inference and optional formatting/teardown,
but excludes microphone capture, UI and the CLI's initial Granite checksum.
Do not add formatting-only RSS to the ASR peak or infer end-user latency from it.

Five-process public-JFK pipeline medians:

| Host | Raw / formatted probe time | Raw / formatted process peak |
| --- | --- | --- |
| Local WSL | 335 / 437 ms | 326 / 326 MiB |
| Linux CI | 756 / 939 ms | 319 / 319 MiB |
| Windows CI | 1,341 / 1,600 ms | 315 / 315 MiB |

Speech processing already dominates the peak in **this particular probe**. These
numbers do not prove zero added memory in every Mika workload, on live microphones,
or on a different computer. Recording and the normal CLI's initial speech-model
checksum are excluded. Raw/formatted runs use the same experimental speech build.

## Validation status

[Native FullStop validation run 39036249265](https://github.com/nochinsky/mika/actions/runs/39036249265)
passed **10 ordinary-build suites plus all 12 prototype suites on each platform**:
Ubuntu 22.04 and Windows Server 2022. Both platforms independently generated the
same pinned INT8 model hash and exactly the same outputs on all 90 authored
examples. The original failed quality gate remains a separate research finding,
not an engineering-test failure or default approval.

Local validation also passed 10 ordinary-build suites, 12 prototype suites and
**all 12 ASan/UBSan suites**, with leak detection enabled and no suppressions.
Third-party libraries are not themselves instrumented. Tests include source-offset
rendering, protected literals/unknown pieces, a 32,767-byte/16,384-word input,
window seams, every cancellation checkpoint, injected exceptions/unsafe output,
asset integrity, Unicode relocation, PTY/classic-console controls, raw default,
public-speech ASR-to-formatting and the complete 300-second repetition regression.
A separate local native exact-32,768-byte run and a source-installed Unicode-path
fake-audio PTY smoke also passed. None records a microphone or establishes natural
five-minute dictation accuracy. Source code validated by CI: `f6059df`.

Workflow **Build and test**, manual input `punctuation=true`, runs ordinary package
checks first, then this opt-in prototype on both platforms and uploads quality,
formatting-resource, public-file-pipeline reports and test logs only. It never
publishes a punctuation binary/release. Main and the public v0.1.2 installer are
unchanged; this remains the separate `prototype/fullstop` branch.

## Provenance and licenses

Exact hashes/URLs: [fetcher](../scripts/fetch_punctuation.py). The English model
and unchanged vocabulary are pinned to
[revision b26fd1c40e88678859048898218ea4edcc24c84a](https://huggingface.co/1-800-BAD-CODE/punctuation_fullstop_truecase_english/tree/b26fd1c40e88678859048898218ea4edcc24c84a).
The author declares Apache-2.0; the fetched model card/configuration and license
are retained. The modified INT8 model is explicitly documented in
[fullstop-NOTICE.txt](../licenses/fullstop-NOTICE.txt), including conversion method
and original/derived hashes. No retraining took place.

Native CPU ONNX Runtime **1.28.2** (MIT plus third-party notices) is extracted from
the pinned sherpa-onnx **v1.13.8** no-TTS SDK; no Sherpa inference library is
linked/deployed. Runtime source: <https://github.com/microsoft/onnxruntime/tree/v1.28.2>.
Native SentencePiece **v0.2.1**, commit
[31646a467d2051eb904e0b45de3a73e91fe1c1e3](https://github.com/google/sentencepiece/tree/31646a467d2051eb904e0b45de3a73e91fe1c1e3),
is Apache-2.0 with protobuf-lite/Abseil/Darts notices. This self-contained version
avoids newer upstream build scripts' automatic Abseil checkout. Source is not
modified; only its inference library is linked. Preserve all actual component
notices/source-availability obligations when redistributing.

The source renderer/bridge is original Mika MIT code, informed by the model's
[Apache-2.0 reference tagging conventions](https://github.com/1-800-BAD-CODE/punctuators/tree/e0723a4f5dfe5f4fac8571a916ea03571b87edd3).

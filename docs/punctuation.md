# Formatting

Mika applies **English FullStop INT8** after recognition to restore punctuation
and capitalization. `mika --raw` skips formatting, including its integrity checks
and runtime loading. There is one fixed formatter and no model selector.

This is a readability pass, not an editor. It cannot correct misheard words or
guarantee meaning. The model supports commas, periods and question marks, not
exclamation marks. There is no dictionary, forced final period, LLM rewrite or
cloud fallback.

## Preservation and fallback

The renderer projects predictions onto original source offsets rather than
reconstructing words. Unknown pieces retain their original characters; unalignable
normalization retains source case. Punctuation is added only at complete-word
boundaries, not inside acronyms or existing literals.

An independent guard permits only the same words/order, ordinary ASCII case changes,
normalized whitespace and at most one appended comma/period/question mark per word.
Original punctuation, digits, spelling, apostrophes and hyphens remain intact.
Paths, emails, numeric tokens, code markers, internal dots/colons, leading-hyphen
flags, camelCase/PascalCase and uppercase acronyms retain source case. A bare
identifier is not necessarily recognizable as code.

A second guard rejects a **new internal period/question mark immediately after an
English negation or its next word**: `not`, `no`, `never`, `without`, `cannot` and
ASCII `n't` contractions. It discards the whole candidate, not individual marks.
Original boundaries and final punctuation remain allowed. This can reject valid
breaks and is not a scope parser; it cannot recover a missing ASR negation.

Input is ASCII, at most **32,768 bytes / 96 bytes per word**. Unsupported text stays
raw. Sequential 254-subword windows with 16 overlap bound attention memory and
preserve source indices. CPU inference uses one intra-op/inter-op thread.

Mika releases ASR/capture resources before loading the formatter. Model/vocabulary
size and SHA-256 are verified. Modules load from the executable's sibling
`punctuation/` directory. Data, loader, inference, allocation and output-rejection
failures preserve raw text with a stderr warning. Cancellation prints no transcript.
Native crashes, aborts and OS termination cannot be recovered in-process.

Current source adds a caller-owned, bounded loader diagnostic naming the library
or missing export, with POSIX loader text or a Windows error code. Controls and
non-ASCII bytes are escaped; local OS paths may appear. Dictated text and inference
exception messages are not included. This is not in the v0.3.1 binary. On Mac,
[security approval](macos.md#first-run-security-approval) is one possible cause of a
load failure; missing/damaged files need repair instead.

Modules remain mapped until exit to avoid runtime/tokenizer registry and TLS
teardown hazards. Sessions, tensors and returned text are freed normally. This
creates no resident service.

## Quality and limitations

The original [30 references](../tests/punctuation_cases.json) and
[additional 60](../tests/punctuation_holdout.json) are unchanged:

| Metric | Original 30 | Additional 60 |
| --- | ---: | ---: |
| Words/order preserved | 30/30 | 60/60 |
| Raw fallback | 0 | 0 |
| Punctuation F1 | 80.4% | 90.0% |
| Case-change F1 | 89.7% | 92.0% |
| Expected question marks | 10/10 | 16/16 |
| Extra question marks | 0 | 0 |

The additional set was authored before its first run, but that run informed a
literal-case fix. It is development validation, not an independent blind holdout.
Its SHA-256 is `daa9645bdb832bd9f510efee09161e5a96888636b954154dfc3a709afa752350`.
Predeclared alternatives are reported separately; no references were changed to
improve scores. The negation guard retains these metrics and has a separate
intentional-fallback regression.

The original 90% prose-style targets remain advisory and unmet on the original
set. Release requirements are preservation, cancellation/fallback safety, output
contracts, portable packaging and acceptable costs—not a claim of perfect prose.
[Prompt fixtures](../tests/prompt_cases.json) exercise negations, numbers, constraints
and literals after ASR; they do not establish what a person intended to say.

Known weaknesses include acronym/brand casing, comma splices, sentence boundaries
and disfluency. Formatting can preserve every word and still change meaning.
Neither these small corpora nor repeated public audio establish natural-dictation
accuracy. Review important output.

## Build and measurement

The [build](../CONTRIBUTING.md) fetches pinned FP32 weights and reproduces the INT8
conversion. The verified model, vocabulary, CPU runtime, native bridge and notices
ship in `bin/punctuation/`. Installed Mika requires no Python or conversion and
performs no formatting download/upload. Mac uses the same weights and CPU session;
its upstream runtime contains unused Core ML support, not selected inference.

```sh
python3 scripts/evaluate_punctuation.py --probe build/bin/mika-punctuation-test \
  --assets build/bin/punctuation --output build/quality-report.json
python3 scripts/benchmark_punctuation.py --probe build/bin/mika-punctuation-test \
  --assets build/bin/punctuation --output build/resource-report.json
```

Use `--corpus tests/punctuation_holdout.json` for the additional set. Windows uses
`python` and `build/bin/Release/*.exe`. Full formatter timing includes integrity,
loading, tokenization, inference, rendering and teardown. Peak RSS is whole-process,
not incremental ASR memory. See [measurement methods](validation.md) and the
[dated Linux results](laptop-validation.md) for resource scopes and reproducible costs.

## Provenance and licenses

Exact URLs and hashes are in the [fetcher](../scripts/fetch_punctuation.py).
FullStop English [revision b26fd1c40e88678859048898218ea4edcc24c84a](https://huggingface.co/1-800-BAD-CODE/punctuation_fullstop_truecase_english/tree/b26fd1c40e88678859048898218ea4edcc24c84a)
is author-declared Apache-2.0. Its card/configuration, license and
[modification notice](../licenses/fullstop-NOTICE.txt) describe the derived INT8
weights; no retraining occurred.

CPU ONNX Runtime **1.28.2** is MIT with third-party notices, from pinned
sherpa-onnx **v1.13.8** no-TTS SDK binaries. No Sherpa inference library is deployed.
[Runtime source](https://github.com/microsoft/onnxruntime/tree/v1.28.2).
SentencePiece **v0.2.1**, commit
[31646a467d2051eb904e0b45de3a73e91fe1c1e3](https://github.com/google/sentencepiece/tree/31646a467d2051eb904e0b45de3a73e91fe1c1e3),
is statically built unmodified with internal dependencies. Preserve its Apache-2.0
and protobuf-lite/Abseil/Darts notices and source-availability obligations.

Mika's renderer/bridge is original MIT code, informed by
[Apache-2.0 tagging conventions](https://github.com/1-800-BAD-CODE/punctuators/tree/e0723a4f5dfe5f4fac8571a916ea03571b87edd3).

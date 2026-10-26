# First offline results — 26 October 2026

Prototype on the `experiment/continuous-sessions` branch, using the installed
Windows Mika 0.3.2 CPU libraries and pinned Granite/Silero weights. Intel Core
i7-13700K (16 cores/24 logical processors), approximately 32 GiB installed RAM.
MSVC 19.44, C17 `/O2 /W4 /WX`. Ordinary desktop conditions, not an isolated
performance benchmark. Each evaluation below used a fresh process. These are
single-run development results, not statistical estimates or hardware acceptance.

The native unit test simulated 30 minutes at 16 kHz and checked **all 28,800,000
PCM samples**, contiguous frame offsets, ready-buffer backpressure and bounded
allocation. It exercised forced and pause boundaries and a final short tail.

## Public repeated-speech regression

The input is the known upstream 11-second public JFK fixture, SHA-256
`59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e`.
References were declared before recognition and were not adjusted. The 132-second
case concatenates 12 copies without extra silence. The ten- and thirty-minute
cases repeat 40/120 fifteen-second slots, each containing the sample and four
seconds of added silence. This is not varied long-form human dictation.

| Input | Segmentation | Word errors / reference words | Process peak RSS | Whole evaluator time |
| --- | --- | ---: | ---: | ---: |
| 132 s | Whole file | 1 / 264 (0.38%) | 689.9 MiB | 3.88 s |
| Same 132 s | Fixed 30 s | 0 / 264 | 394.9 MiB | 3.67 s |
| Same 132 s | Fixed 60 s | 2 / 264 (0.76%) | 482.3 MiB | 3.57 s |
| Same 132 s | Pause-first, max 60 s | 0 / 264 | 350.0 MiB | 4.72 s |
| 10 min | Pause-first, max 60 s | 0 / 880 | 353.6 MiB | 18.55 s |
| 30 min | Pause-first, max 60 s | 0 / 2,640 | 353.2 MiB | 58.02 s |

Pause-first settings: minimum 10 seconds, speech probability >= 0.5, 800 ms
consecutive non-speech. The audio buffer was 3,840,000 bytes (3.66 MiB) for every
60-second setting. The complete evaluator includes weight verification, Python
file reading/conversion, VAD, ASR, concatenation, PCM integrity checks and WER;
it does not include a microphone or formatting. Thirty-minute ASR/admission time
alone was 43.90 seconds. Transcript accumulation still consumes growing text memory.

Every run preserved the complete original PCM bit-for-bit and in order. The
whole-file hypothesis contained 11 instances of `not` versus 12 in the reference;
fixed 60-second chunks contained 10. All three pause-first runs and the fixed
30-second case retained their expected `not` counts.
These count checks are review flags, not proof of preserved meaning.

Do not select a production chunk size from this fixture. Both a short whole-file
ASR error and an additional fixed-cut negation loss occurred despite correct PCM.

## Separate synthetic boundary stress

One 27.385-second file was generated locally from the frozen `synthetic-case.txt`
text using Windows System.Speech, Microsoft David Desktop at rate 0, mono
16-bit/16 kHz. This is **synthesized speech**, not a human accuracy benchmark.
The reference contains 58 words and was written before synthesis/recognition.

| Strategy | Strict word errors | Comparison |
| --- | ---: | --- |
| Whole file | 8 / 58 (13.79%) | Number spellings became numerals |
| Fixed 10 s | 10 / 58 (17.24%) | Added a broken word across a forced cut |
| Pause-first, min 5 s/max 15 s, 800 ms | 8 / 58 (13.79%) | Identical raw hypothesis to whole-file result |

The whole/pause-first outputs preserved the instructions and number values in
this one case, but strict scoring retains the eight spelling-to-numeral edits.
The fixed-cut output split `publishing` into `public doishing`. No reference
alternatives or literal transcript fixes were added after observing it.

## Decision

The first prototype supports the **feasibility of bounded audio storage and
long offline sessions**. Pause-aligned chunks performed well on these narrow
fixtures. It is **not ready to replace the production limit**: continuous speech
can still force unsafe cuts, and no live capture queue, cancellation/UI loop,
formatter boundary validation or natural-dictation corpus has been accepted.

Keep the branch experimental. The next gate is varied boundary-focused speech
plus an explicit policy for recordings with no safe pause; only then integrate
a bounded capture queue and the normal Enter/Esc workflow.

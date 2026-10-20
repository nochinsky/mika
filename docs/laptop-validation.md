# Linux performance snapshot

Measurements from **2026-10-18**, with a speech-admission follow-up on
**2026-10-19**. These are dated local-source-build results, not current-release
certification or natural-dictation accuracy. See [validation methods](validation.md)
to reproduce them.

## Environment

- Intel Core Ultra 5 125H, 14 cores / 18 logical CPUs, approximately 16 GB RAM.
- Linux x86-64, kernel 7.2.10, PipeWire 1.6.9.
- Plugged in, CPU governor `powersave`, ordinary desktop workloads; no thermal
  isolation or governor/global-cache/kernel changes.
- GCC 16.2.1, CMake 4.4.4, project-local Python 3.12.14.
- Baseline source `8721960` plus validation tooling, Release mode,
  `MIKA_NATIVE_CPU=ON`, system curl/crypto and pinned assets. Not a portable bundle.
- Existing verified model reused; no installed app, profiles or OS packages changed
  during these measurements.

```sh
cmake -S . -B build-laptop -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DMIKA_NATIVE_CPU=ON -DPython3_EXECUTABLE="$PWD/build-tools/bin/python" \
  -DMIKA_TEST_MODEL="$HOME/.local/share/mika/models/granite-speech-5.0-470m-turboctc-Q4_K_M.gguf"
cmake --build build-laptop --parallel 4
ctest --test-dir build-laptop --output-on-failure
```

## Regression and microphone checks

The baseline passed 16/16 native and 12/12 model-free tests, including ASan/UBSan
on owned code. Source install/relocation with spaces/Unicode passed version and
public-file raw/formatted inference. Public JFK produced 0% normalized WER in a
scorer smoke test; it was already a known fixture, not a blind accuracy benchmark.
These historical counts do not describe the expanded current suite.

Five fresh real CLI processes per cache mode used the default analog input,
waited 1.2 seconds after Listening and cancelled with Esc. No audio/transcripts
were saved or uploaded.

| Cache mode | Median launch → observed Listening | Median Esc → exit | Median whole-process peak RSS |
| --- | ---: | ---: | ---: |
| Ordinary caches | 248.4 ms | 4.7 ms | 295.3 MiB |
| File-local eviction requested | 350.7 ms | 9.3 ms | 294.1 MiB |

All ten runs received at least one second of frames, returned 130, emitted no
stdout and restored the terminal. This proves sample delivery/cancellation, not
correct input choice or intelligibility. Timing includes scheduler/PTY overhead;
a fully cold system was not measured.

## File pipeline

Five fresh processes per duration/mode/cache combination used exact-length repeated
public JFK audio. Includes checksum, decoding, speech loading/inference, optional
formatting and teardown. **Excludes microphone/console overhead and live
Enter-to-output timing.** RSS is whole-process.

| Input | Cache mode | Raw median | Formatted median | Raw RSS median | Formatted RSS median |
| --- | --- | ---: | ---: | ---: | ---: |
| 10 s | Ordinary | 0.601 s | 0.727 s | 321.5 MiB | 322.4 MiB |
| 10 s | Eviction requested | 0.710 s | 0.876 s | 321.8 MiB | 321.9 MiB |
| 60 s | Ordinary | 2.373 s | 2.555 s | 468.2 MiB | 469.4 MiB |
| 60 s | Eviction requested | 2.551 s | 2.746 s | 469.8 MiB | 469.4 MiB |
| 300 s | Ordinary | 11.672 s | 12.041 s | 1186.7 MiB | 1189.8 MiB |
| 300 s | Eviction requested | 11.784 s | 11.959 s | 1185.7 MiB | 1186.6 MiB |

Eviction was best-effort `POSIX_FADV_DONTNEED`, not guaranteed cold caches.
Checksum medians were about 154–158 ms ordinary versus 255–260 ms after eviction;
checksum plus model load was 221–228 versus 326–330 ms. Run order and desktop load
can affect differences. Only completed five-run groups are included; an interrupted
long-duration invocation was rerun. The separate five-minute regression retained
all expected public-speech segments and the final phrase in both modes.

## Formatting

All 90 public examples preserved words/order with zero fallbacks. Original/additional
punctuation F1 was 80.4%/90.0%; case F1 89.7%/92.0%; question recall 10/10 and 16/16,
with no extra questions. References were unchanged; advisory original targets
remain unmet. See [formatting limitations](punctuation.md#quality-and-limitations).

Five-process median full formatting-stage cost was **135.8 ms / 121.1 MiB** for
18 words and **263.8 ms / 121.3 MiB** for 748 repeated-public-speech words. Memory
is whole-process, not additive to ASR. The local payload was 82,021,715 bytes;
compiled module size varies by build.

## Speech-admission follow-up

Integration `acdb693` plus provisioning fixes `4b08b9d` passed 21/21 full Linux and
15/15 model-free groups. Owned runtime/policy passed 15/15 ASan/UBSan groups before
the provisioning-only fixes. These were local checks, not native Mac/Windows
acceptance at that source revision.

The classifier rejected nine deterministic synthetic non-speech inputs and admitted
five public-speech variants, including 1% amplitude and one second of speech with
pauses. Missing/truncated/wrong-hash VAD data failed closed in both modes.
Admission was not accuracy: attenuated ASR could lose words including “not.”

Three alternating fresh processes per mode used the same 11-second public JFK
file, ordinary caches and the same laptop/power policy:

| Mode | Pre-gate baseline median | Gated median | Baseline / gated RSS medians |
| --- | ---: | ---: | ---: |
| Raw | 706.0 ms | 716.2 ms | 328.7 / 333.9 MiB |
| Default | 833.0 ms | 840.6 ms | 327.1 / 330.7 MiB |

The gate took about 10.7–11.1 ms and adds a verified 1,241,056-byte model. This is
a small-sample cost estimate, not a confidence interval or ASR speedup. Full Granite
hashing remains enabled. No private speech was used for these measurements.

## Limits

No validated clean human-dictation benchmark is established by this report.
Meaning, technical literals, disfluency, multiple speakers/noise conditions and
live spoken-prompt latency require separately consented evaluation. Microphone
startup and repeated public files must not be presented as that evidence.

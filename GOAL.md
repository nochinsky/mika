# Mika's scope

Mika turns spoken English into a usable prompt for AI agents with minimal friction:
**run `mika`, speak, press Enter, get text, exit.**

## Priorities

1. Fast startup/transcription and sensible CPU, memory, and download costs.
2. A reliable one-shot CLI: transcript on stdout, status/errors on stderr.
3. Offline operation after the consented first speech-model download. No audio
   uploads, saved recordings, accounts, telemetry, or background service.
4. One fixed CPU speech model (Granite Speech 5.0 470M TurboCTC Q4_K_M) and one
   fixed lightweight formatter (English FullStop INT8). `--raw` skips formatting.
5. Preserve the ASR transcript's words/order through formatting. Formatting may
   change ordinary ASCII case/add permitted punctuation, but cannot rewrite words.
   Obvious literals retain their source case. This does not prevent ASR mishearing.
6. Enter finishes; Esc/Ctrl+C cancels without a transcript. Five minutes ends
   recording automatically. No-speech/failure must not submit an empty agent prompt.
7. Straightforward per-user installation and explicit safe updates on x86-64
   Linux/WSL (glibc 2.35+) and Windows 10/11. Experimental macOS 14+ Apple Silicon
   support uses the same CPU-only pipeline; native CI does not establish microphone
   permissions/capture. No root/admin or end-user Python.

## Deliberate non-goals

Publication-ready prose, guaranteed semantic accuracy, spelling/name dictionaries,
LLM editing, multiple model modes, GPU requirements, long-form chunking, settings
wizards/configuration files, clipboard access, simulated typing, and built-in agent
integrations. Unix-style stdout/exit codes are the integration boundary.

Keep quality/reference scores as honest regression measurements. Release decisions
weigh prompt usefulness and measured resource costs, with safety and reliability
as hard requirements—not an arbitrary prose-style score as a proxy for utility.
Do not alter old references or force punctuation just to make a score pass.

Prefer fixing observed problems over adding speculative options or abstractions.
Source/build/test tooling may use Python; the installed application must not.

# Scope

Mika is a focused English dictation CLI for **Mac, Linux and Windows**:
**run → speak → Enter → transcript on stdout → exit**. Mac support is experimental.

## Priorities

1. Fast startup and transcription with reasonable CPU, memory and download costs.
2. A reliable one-shot CLI: text on stdout, status/errors on stderr, documented exits.
3. Offline operation after a consented first model download. No accounts, telemetry,
   audio uploads, saved recordings or background service in the installed runtime.
4. One fixed CPU pipeline: Granite Speech 5.0 470M TurboCTC Q4_K_M, verified Silero
   speech admission and English FullStop INT8 formatting. `--raw` skips only formatting.
5. Preserve recognized words/order and obvious literals through formatting. Never
   guess identifiers, repair spelling or imply guaranteed meaning/recognition accuracy.
6. Enter finishes; Esc/Ctrl+C cancels without a transcript. Recording is bounded at
   five minutes. No-speech and operational failures do not publish transcripts.
7. Per-user installation, explicit updates and safe removal without administrator
   access or end-user Python. Respect platform permission and security controls.

## Non-goals

Publication-ready prose, guaranteed semantic accuracy, dictionaries, LLM rewriting,
model menus, GPU requirements, long-form chunking, configuration wizards, clipboard
access, simulated typing and automatic agent integrations. Stdout and exit codes
are the integration boundary; success is not permission to execute dictated text.

Fix observed problems rather than adding speculative options or abstractions.
Preserve references and report honest quality/resource measurements. Safety and
reliability are release requirements; style scores are not a substitute for them.
Development tools may use Python and explicitly consented private recordings;
the installed application must require neither.

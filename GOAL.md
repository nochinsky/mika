# Mika project

## Agreed v1 scope

The discussion following this original proposal settled on:

- A C17 application using transcribe.cpp through its C API (C++17 internals).
- One fixed English model: standard Apache-2.0 Granite Speech 5.0 470M TurboCTC Q4_K_M.
- Run `mika`, speak after Listening, press Enter to transcribe, or Esc/Ctrl+C to cancel.
- Print the transcript to the terminal/stdout; **no clipboard or simulated typing**.
- Status messages go to stderr, allowing `mika > notes.txt`.
- Automatic defaults and a consented, verified first-run model download; **no `mika setup`**.
- `mika --help` explains usage; subsequent transcription is offline.
- Audio stays in memory and is discarded after use. The initial implementation has an explicit 60-second auto-finish limit to bound memory.
- Desktop Linux, macOS, and Windows are the source-level targets; native platform validation is required before claiming release support.

See README.md for current build instructions, tests, and limitations.

## Original proposal (historical; agreed scope above takes precedence)

I want to create a speach to text cross platform recognision cli software.

In very basic words I want it to be a C program ( if you have any other language suggestions feel free to tell me) that uses one specific model and its made for only english. Let me explain:

First the model that will be used is: Granite Speech 5.0 Q4_K_M . I chose it because its a model that can work across almost every machine and works fast on cpu and has good english scores. If you have any objections against my choice feel free to tell me.

Next the c program will be hardcoded to use that specific model, it should automatically download the model and place it somewhere where it can access it. maybe .config? or on windows systems somewhere else. Then with our hardcoded settings that should perform well across all devices when the user would type "mika" in the terminal the program would open and a small cli minimalistic looking design would ask wait for user mic input. when the user would be done speaking he would need to press a hotkey or esc or sm like that. and the program should exit and give him the text that he just transcribed. and copy it into his keyboard.

i was thinking istead of fully hardcoding the model settings we could set up a "mika setup" command or something like that. tell me what you think. also was thinking about setting up a "mika --help" command to list those two i suppose.

tell me what you think.
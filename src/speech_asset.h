#ifndef MIKA_SPEECH_ASSET_H
#define MIKA_SPEECH_ASSET_H

#include <stdint.h>

/* Required CPU VAD, not an ASR model. Converted Silero v6.2 F32 weights:
 * https://huggingface.co/handy-computer/silero-vad-v6.2-gguf
 * Immutable revision: a9b2d61c20ae4ddf3644edb34969e8185a485448
 * Source/license provenance: licenses/silero-vad-LICENSE.txt.
 */
#define MIKA_VAD_FILE "silero-vad-v6.2-F32.gguf"
#define MIKA_VAD_BYTES UINT64_C(1241056)
#define MIKA_VAD_SHA256 "0d871a800c420fdd5d1b17a3aea4296d1c39608f0ff4a9295eb76457eb1c88e6"

#endif

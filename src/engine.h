#ifndef MIKA_ENGINE_H
#define MIKA_ENGINE_H

#include <stddef.h>

typedef struct MikaEngine MikaEngine;
typedef int (*MikaCancelled)(void *userdata);
typedef struct {
    double speech_gate_ms, inference_ms;
    int speech_admitted;
} MikaEngineTimings;

/* Mandatory bundled CPU speech detection precedes ASR, also in raw mode.
 * Return 3 for no detected speech, 1 for failures, 130 for cancellation.
 * The returned transcript is borrowed until close or the next run. */
int mika_engine_open(const char *model_path, MikaCancelled cancelled, void *userdata,
                     MikaEngine **out);
int mika_engine_run(MikaEngine *engine, const float *pcm, size_t frames,
                    const char **text);
MikaEngineTimings mika_engine_timings(const MikaEngine *engine);
void mika_engine_close(MikaEngine *engine);

#endif

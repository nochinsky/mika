#ifndef MIKA_ENGINE_H
#define MIKA_ENGINE_H

#include <stddef.h>

typedef struct MikaEngine MikaEngine;
typedef int (*MikaCancelled)(void *userdata);
typedef struct {
    double speech_gate_ms, inference_ms;
    int speech_admitted;
} MikaEngineTimings;

/* Sequential CPU sessions; callback/userdata live until close. Open returns
 * 0, failure 1 or abort 130 and clears *out on failure. Close accepts NULL. */
int mika_engine_open(const char *model_path, MikaCancelled cancelled, void *userdata,
                     MikaEngine **out);
/* Mandatory bundled speech admission precedes ASR, also in raw mode. PCM is
 * borrowed unchanged for this synchronous call. Returns 0, no speech 3,
 * failure 1 or abort 130. *text is cleared first, then borrowed until next run
 * or close. The caller retains the reason behind a boolean abort callback. */
int mika_engine_run(MikaEngine *engine, const float *pcm, size_t frames,
                    const char **text);
MikaEngineTimings mika_engine_timings(const MikaEngine *engine);
void mika_engine_close(MikaEngine *engine);

#endif

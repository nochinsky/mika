#ifndef MIKA_ENGINE_H
#define MIKA_ENGINE_H

#include <stddef.h>

typedef struct MikaEngine MikaEngine;
typedef int (*MikaCancelled)(void *userdata);

/* The returned transcript is borrowed until close or the next run. */
int mika_engine_open(const char *model_path, MikaCancelled cancelled, void *userdata,
                     MikaEngine **out);
int mika_engine_run(MikaEngine *engine, const float *pcm, size_t frames,
                    const char **text);
void mika_engine_close(MikaEngine *engine);

#endif

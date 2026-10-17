#include "pcm.h"
#include <stdlib.h>
#include <string.h>

int mika_pcm_init(MikaPcm *pcm, unsigned capacity)
{
    pcm->samples = NULL;
    pcm->capacity = capacity;
    mika_atomic_init(&pcm->frames, 0);
    mika_atomic_init(&pcm->failed, 0);
    if (!capacity || capacity > MIKA_MAX_FRAMES) { return 1; }
    pcm->samples = calloc(capacity, sizeof(*pcm->samples));
    return pcm->samples ? 0 : 1;
}

void mika_pcm_append(MikaPcm *pcm, const float *samples, size_t frames)
{
    unsigned current = mika_atomic_get(&pcm->frames);
    if (!frames || current >= pcm->capacity) { return; }
    if (!samples) { mika_atomic_set(&pcm->failed, 1); return; }
    size_t available = pcm->capacity - current;
    size_t count = frames < available ? frames : available;
    memcpy(pcm->samples + current, samples, count * sizeof(*samples));
    mika_atomic_set(&pcm->frames, current + (unsigned)count);
}

void mika_pcm_free(MikaPcm *pcm)
{
    free(pcm->samples);
    pcm->samples = NULL;
}

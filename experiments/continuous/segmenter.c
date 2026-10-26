#include "segmenter.h"
#include <stdlib.h>
#include <string.h>

struct MikaSegmenter {
    float *pcm;
    size_t capacity, minimum, pause, frames, silent;
    uint64_t total, start;
    int speech_seen, ready, finished;
};

MikaSegmenter *mika_segmenter_open(size_t maximum, size_t minimum, size_t pause)
{
    if (!maximum || !minimum || minimum > maximum || maximum > SIZE_MAX / sizeof(float)) {
        return NULL;
    }
    MikaSegmenter *s = calloc(1, sizeof(*s));
    if (!s) { return NULL; }
    s->pcm = malloc(maximum * sizeof(*s->pcm));
    if (!s->pcm) { free(s); return NULL; }
    s->capacity = maximum;
    s->minimum = minimum;
    s->pause = pause;
    return s;
}

void mika_segmenter_close(MikaSegmenter *s)
{
    if (s) { free(s->pcm); free(s); }
}

int mika_segmenter_push(MikaSegmenter *s, const float *pcm, size_t frames,
                        int speech, size_t *consumed)
{
    if (consumed) { *consumed = 0; }
    if (!s || !consumed || s->finished || (frames && !pcm) ||
        (uint64_t)frames > UINT64_MAX - s->total) { return 1; }
    if (s->ready || !frames) { return 0; }
    size_t count = s->capacity - s->frames;
    if (count > frames) { count = frames; }
    memcpy(s->pcm + s->frames, pcm, count * sizeof(*pcm));
    s->frames += count;
    s->total += (uint64_t)count;
    if (speech) { s->speech_seen = 1; s->silent = 0; }
    else { s->silent += count; }
    if (s->frames == s->capacity) { s->ready = MIKA_SEGMENT_LIMIT; }
    else if (s->pause && s->speech_seen && s->frames >= s->minimum && s->silent >= s->pause) {
        s->ready = MIKA_SEGMENT_PAUSE;
    }
    *consumed = count;
    return 0;
}

int mika_segmenter_peek(const MikaSegmenter *s, const float **pcm, size_t *frames,
                        uint64_t *start, int *reason)
{
    if (pcm) { *pcm = NULL; }
    if (frames) { *frames = 0; }
    if (start) { *start = 0; }
    if (reason) { *reason = 0; }
    if (!s || !s->ready) { return 0; }
    if (pcm) { *pcm = s->pcm; }
    if (frames) { *frames = s->frames; }
    if (start) { *start = s->start; }
    if (reason) { *reason = s->ready; }
    return 1;
}

void mika_segmenter_consume(MikaSegmenter *s)
{
    if (s && s->ready) {
        s->frames = s->silent = 0;
        s->speech_seen = s->ready = 0;
        s->start = s->total;
    }
}

int mika_segmenter_finish(MikaSegmenter *s)
{
    if (!s || s->ready) { return 1; }
    s->finished = 1;
    if (s->frames) { s->ready = MIKA_SEGMENT_END; }
    return 0;
}

uint64_t mika_segmenter_total(const MikaSegmenter *s) { return s ? s->total : 0; }
size_t mika_segmenter_audio_bytes(const MikaSegmenter *s)
{
    return s ? s->capacity * sizeof(*s->pcm) : 0;
}

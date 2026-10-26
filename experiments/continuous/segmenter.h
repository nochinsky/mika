#ifndef MIKA_EXPERIMENT_SEGMENTER_H
#define MIKA_EXPERIMENT_SEGMENTER_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32) && defined(MIKA_SEGMENTER_SHARED)
#ifdef MIKA_SEGMENTER_BUILD
#define MIKA_SEGMENT_API __declspec(dllexport)
#else
#define MIKA_SEGMENT_API __declspec(dllimport)
#endif
#else
#define MIKA_SEGMENT_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct MikaSegmenter MikaSegmenter;
enum { MIKA_SEGMENT_LIMIT = 1, MIKA_SEGMENT_PAUSE = 2, MIKA_SEGMENT_END = 3 };

/* Worker-thread component, not a real-time capture callback. No session timer.
 * Holds exactly max_frames floats. VAD is supplied by the caller per input block.
 * silence_frames == 0 disables pause cuts. Nothing is trimmed or overlapped. */
MIKA_SEGMENT_API MikaSegmenter *mika_segmenter_open(size_t max_frames,
    size_t min_frames, size_t silence_frames);
MIKA_SEGMENT_API void mika_segmenter_close(MikaSegmenter *segmenter);
/* Returns 1 for invalid input/finished state. *consumed may be less than frames;
 * drain a ready chunk before retrying the remainder. Ready data is never overwritten.
 * No allocation, inference, waiting or transcript publication happens here. */
MIKA_SEGMENT_API int mika_segmenter_push(MikaSegmenter *segmenter,
    const float *pcm, size_t frames, int speech, size_t *consumed);
/* Returned PCM is borrowed and stable until consume/close. Frame offsets are
 * contiguous across chunks and use 64 bits; total session length does not grow RAM. */
MIKA_SEGMENT_API int mika_segmenter_peek(const MikaSegmenter *segmenter,
    const float **pcm, size_t *frames, uint64_t *start, int *reason);
MIKA_SEGMENT_API void mika_segmenter_consume(MikaSegmenter *segmenter);
/* Finish after draining any ready chunk; exposes a remaining tail, even a short
 * or silent one. The caller must handle the recognizer's minimum input length. */
MIKA_SEGMENT_API int mika_segmenter_finish(MikaSegmenter *segmenter);
MIKA_SEGMENT_API uint64_t mika_segmenter_total(const MikaSegmenter *segmenter);
MIKA_SEGMENT_API size_t mika_segmenter_audio_bytes(const MikaSegmenter *segmenter);

#ifdef __cplusplus
}
#endif
#endif

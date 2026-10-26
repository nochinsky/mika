#include "segmenter.h"
#include <stdio.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

static int boundaries(void)
{
    CHECK(!mika_segmenter_open(0, 1, 0));
    CHECK(!mika_segmenter_open(4, 0, 0));
    CHECK(!mika_segmenter_open(4, 5, 0));
    CHECK(!mika_segmenter_open(SIZE_MAX, 1, 0));
    MikaSegmenter *s = mika_segmenter_open(4, 2, 2);
    CHECK(s && mika_segmenter_audio_bytes(s) == 4 * sizeof(float));
    float input[] = {1, 2, 3, 4, 5, 6};
    size_t consumed = 99, frames = 99;
    uint64_t start = 99;
    const float *pcm = input;
    int reason = 99;
    CHECK(mika_segmenter_push(s, NULL, 1, 0, &consumed) == 1 && consumed == 0);
    CHECK(mika_segmenter_push(s, NULL, 0, 0, &consumed) == 0 && consumed == 0);
    CHECK(!mika_segmenter_push(s, input, 1, 1, &consumed) && consumed == 1);
    CHECK(!mika_segmenter_peek(s, &pcm, &frames, &start, &reason));
    CHECK(pcm == NULL && frames == 0 && reason == 0);
    CHECK(!mika_segmenter_push(s, input + 1, 2, 0, &consumed) && consumed == 2);
    CHECK(mika_segmenter_peek(s, &pcm, &frames, &start, &reason));
    CHECK(frames == 3 && start == 0 && reason == MIKA_SEGMENT_PAUSE);
    CHECK(!memcmp(pcm, input, 3 * sizeof(float)));
    CHECK(!mika_segmenter_push(s, input + 3, 3, 1, &consumed) && consumed == 0);
    CHECK(!memcmp(pcm, input, 3 * sizeof(float))); /* Backpressure cannot overwrite it. */
    CHECK(mika_segmenter_finish(s) == 1); /* Drain first, never discard a ready chunk. */
    mika_segmenter_consume(s);
    CHECK(!mika_segmenter_push(s, input + 3, 3, 1, &consumed) && consumed == 3);
    CHECK(!mika_segmenter_finish(s));
    CHECK(mika_segmenter_peek(s, &pcm, &frames, &start, &reason));
    CHECK(start == 3 && frames == 3 && reason == MIKA_SEGMENT_END);
    CHECK(!memcmp(pcm, input + 3, 3 * sizeof(float)));
    CHECK(mika_segmenter_total(s) == 6);
    mika_segmenter_consume(s);
    CHECK(!mika_segmenter_peek(s, &pcm, &frames, &start, &reason));
    CHECK(mika_segmenter_push(s, input, 1, 1, &consumed) == 1);
    mika_segmenter_close(s);
    mika_segmenter_close(NULL);
    return 0;
}

static int long_session(void)
{
    /* 30 minutes at 16 kHz, fed in awkward blocks. Check every sample and offset.
       No microphone, model, network, clock delays or growing allocation. */
    const uint64_t total = UINT64_C(30) * 60 * 16000;
    const size_t capacity = 60001;
    MikaSegmenter *s = mika_segmenter_open(capacity, 32000, 12000);
    CHECK(s);
    float block[997];
    uint64_t fed = 0, read = 0;
    unsigned chunks = 0, pauses = 0, forced = 0;
    while (fed < total) {
        size_t count = (size_t)((total - fed) < 997 ? total - fed : 997);
        for (size_t i = 0; i < count; ++i) { block[i] = (float)((fed + i) % 65521); }
        size_t offset = 0;
        while (offset < count) {
            size_t consumed;
            int speech = ((fed / 16000) % 7) < 5;
            CHECK(!mika_segmenter_push(s, block + offset, count - offset, speech, &consumed));
            offset += consumed;
            const float *pcm;
            size_t frames;
            uint64_t start;
            int reason;
            if (mika_segmenter_peek(s, &pcm, &frames, &start, &reason)) {
                CHECK(frames <= capacity && start == read);
                for (size_t i = 0; i < frames; ++i) { CHECK(pcm[i] == (float)((read + i) % 65521)); }
                read += frames;
                ++chunks;
                if (reason == MIKA_SEGMENT_PAUSE) { ++pauses; }
                if (reason == MIKA_SEGMENT_LIMIT) { ++forced; }
                mika_segmenter_consume(s);
            } else { CHECK(consumed > 0); }
        }
        fed += count;
    }
    CHECK(!mika_segmenter_finish(s));
    const float *pcm;
    size_t frames;
    uint64_t start;
    int reason;
    if (mika_segmenter_peek(s, &pcm, &frames, &start, &reason)) {
        CHECK(start == read && reason == MIKA_SEGMENT_END);
        for (size_t i = 0; i < frames; ++i) { CHECK(pcm[i] == (float)((read + i) % 65521)); }
        read += frames;
        mika_segmenter_consume(s);
    }
    CHECK(read == total && mika_segmenter_total(s) == total);
    CHECK(chunks > 100 && pauses > 0 && forced > 0);
    CHECK(mika_segmenter_audio_bytes(s) == capacity * sizeof(float));
    mika_segmenter_close(s);
    puts("PASS: 30-minute synthetic PCM session, every sample/offset preserved, bounded buffer");
    return 0;
}

static int silent_and_short_tail(void)
{
    MikaSegmenter *s = mika_segmenter_open(5, 2, 1);
    CHECK(s);
    float zeros[7] = {0};
    size_t consumed;
    CHECK(!mika_segmenter_push(s, zeros, 7, 0, &consumed) && consumed == 5);
    const float *pcm;
    size_t frames;
    uint64_t start;
    int reason;
    CHECK(mika_segmenter_peek(s, &pcm, &frames, &start, &reason) && reason == MIKA_SEGMENT_LIMIT);
    mika_segmenter_consume(s);
    CHECK(!mika_segmenter_push(s, zeros, 1, 0, &consumed) && consumed == 1);
    CHECK(!mika_segmenter_finish(s));
    CHECK(mika_segmenter_peek(s, &pcm, &frames, &start, &reason));
    CHECK(frames == 1 && start == 5 && reason == MIKA_SEGMENT_END);
    mika_segmenter_consume(s);
    CHECK(!mika_segmenter_finish(s));
    mika_segmenter_close(s);
    return 0;
}

int main(void)
{
    if (boundaries() || long_session() || silent_and_short_tail()) { return 1; }
    puts("PASS: invalid input, pause/forced/final boundaries, backpressure, silent/short tails");
    return 0;
}

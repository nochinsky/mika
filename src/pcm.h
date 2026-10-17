#ifndef MIKA_PCM_H
#define MIKA_PCM_H

#include <stddef.h>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
typedef volatile LONG MikaAtomic;
static inline void mika_atomic_init(MikaAtomic *value, unsigned number) { *value = (LONG)number; }
static inline unsigned mika_atomic_get(MikaAtomic *value)
{ return (unsigned)InterlockedCompareExchange(value, 0, 0); }
static inline void mika_atomic_set(MikaAtomic *value, unsigned number)
{ InterlockedExchange(value, (LONG)number); }
#else
#include <stdatomic.h>
typedef atomic_uint MikaAtomic;
static inline void mika_atomic_init(MikaAtomic *value, unsigned number) { atomic_init(value, number); }
static inline unsigned mika_atomic_get(MikaAtomic *value)
{ return atomic_load_explicit(value, memory_order_acquire); }
static inline void mika_atomic_set(MikaAtomic *value, unsigned number)
{ atomic_store_explicit(value, number, memory_order_release); }
#endif

#define MIKA_SAMPLE_RATE 16000u
#define MIKA_MAX_SECONDS 60u
#define MIKA_MAX_FRAMES (MIKA_SAMPLE_RATE * MIKA_MAX_SECONDS)

typedef struct {
    float *samples;
    unsigned capacity;
    MikaAtomic frames;
    MikaAtomic failed;
} MikaPcm;

int mika_pcm_init(MikaPcm *pcm, unsigned capacity);
/* Single producer only. Does not allocate, lock, or write beyond capacity. */
void mika_pcm_append(MikaPcm *pcm, const float *samples, size_t frames);
void mika_pcm_free(MikaPcm *pcm);

#endif

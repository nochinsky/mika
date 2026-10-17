#ifndef MIKA_AUDIO_H
#define MIKA_AUDIO_H

#include <stddef.h>

typedef struct MikaAudio MikaAudio;
int mika_audio_start(MikaAudio **audio);
int mika_audio_failed(MikaAudio *audio);
size_t mika_audio_frames(MikaAudio *audio);
const float *mika_audio_samples(MikaAudio *audio);
/* Stop joins the producer before the main thread reads/releases audio storage. */
void mika_audio_stop(MikaAudio *audio);
void mika_audio_close(MikaAudio *audio);

#endif

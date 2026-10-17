#include "audio.h"
#include "pcm.h"
#include "platform.h"
#include "miniaudio.h"

#include <stdio.h>
#include <stdlib.h>

struct MikaAudio {
    ma_context context;
    ma_device device;
    MikaPcm pcm;
    MikaAtomic stopping;
    int context_ready, device_ready, started;
};

static void capture(ma_device *device, void *output, const void *input, ma_uint32 frames)
{
    (void)output;
    MikaAudio *audio = device->pUserData;
    mika_pcm_append(&audio->pcm, input, frames);
}

static void notification(const ma_device_notification *event)
{
    MikaAudio *audio = event->pDevice->pUserData;
    if (event->type == ma_device_notification_type_stopped &&
        !mika_atomic_get(&audio->stopping)) {
        mika_atomic_set(&audio->pcm.failed, 1);
    }
}

int mika_audio_start(MikaAudio **out)
{
    *out = NULL;
    MikaAudio *audio = calloc(1, sizeof(*audio));
    if (!audio) {
        mika_status_clear();
        fputs("mika: not enough memory for microphone capture.\n", stderr);
        return 1;
    }
    mika_atomic_init(&audio->stopping, 0);
    if (mika_pcm_init(&audio->pcm, MIKA_MAX_FRAMES)) {
        mika_status_clear();
        fputs("mika: not enough memory for the recording buffer.\n", stderr);
        goto failed;
    }
    ma_result result = ma_context_init(NULL, 0, NULL, &audio->context);
    if (result != MA_SUCCESS) {
        mika_status_clear();
        fprintf(stderr, "mika: no usable audio backend: %s.\n", ma_result_description(result));
        goto failed;
    }
    audio->context_ready = 1;
    ma_device_config config = ma_device_config_init(ma_device_type_capture);
    config.capture.format = ma_format_f32;
    config.capture.channels = 1;
    config.sampleRate = MIKA_SAMPLE_RATE;
    config.dataCallback = capture;
    config.notificationCallback = notification;
    config.pUserData = audio;
    result = ma_device_init(&audio->context, &config, &audio->device);
    if (result != MA_SUCCESS) {
        mika_status_clear();
        fprintf(stderr, "mika: cannot open the default microphone: %s.\n"
                        "      Check the system input device and microphone permissions.\n",
                ma_result_description(result));
        goto failed;
    }
    audio->device_ready = 1;
    result = ma_device_start(&audio->device);
    if (result != MA_SUCCESS) {
        mika_status_clear();
        fprintf(stderr, "mika: cannot start microphone capture: %s.\n", ma_result_description(result));
        goto failed;
    }
    audio->started = 1;
    *out = audio;
    return 0;
failed:
    mika_audio_close(audio);
    return 1;
}

int mika_audio_failed(MikaAudio *audio) { return mika_atomic_get(&audio->pcm.failed) != 0; }
size_t mika_audio_frames(MikaAudio *audio) { return mika_atomic_get(&audio->pcm.frames); }
const float *mika_audio_samples(MikaAudio *audio) { return audio->pcm.samples; }

void mika_audio_stop(MikaAudio *audio)
{
    if (audio && audio->device_ready) {
        mika_atomic_set(&audio->stopping, 1);
        if (audio->started && ma_device_stop(&audio->device) != MA_SUCCESS) {
            mika_atomic_set(&audio->pcm.failed, 1);
        }
        /* Uninitialization joins the device thread even if stop reported an error. */
        ma_device_uninit(&audio->device);
        audio->device_ready = 0;
        audio->started = 0;
    }
}

void mika_audio_close(MikaAudio *audio)
{
    if (audio) {
        mika_audio_stop(audio);
        if (audio->context_ready) { ma_context_uninit(&audio->context); }
        mika_pcm_free(&audio->pcm);
        free(audio);
    }
}

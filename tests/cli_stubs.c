/* Test-only dependencies for the real main/platform code. No audio or network I/O. */
#include "audio.h"
#include "engine.h"
#include "model.h"
#include "pcm.h"
#include "platform.h"
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

struct MikaAudio { MikaPcm pcm; };
struct MikaEngine { MikaCancelled cancelled; void *userdata; char *text; };

int mika_model_ensure(MikaTerminal *terminal, char **path)
{
    (void)terminal;
    if (getenv("MIKA_FIXTURE_MODEL_ERROR")) { return 1; }
    *path = malloc(16);
    if (!*path) { return 1; }
    strcpy(*path, "fixture.gguf");
    return 0;
}

int mika_audio_start(MikaAudio **out)
{
    if (getenv("MIKA_FIXTURE_AUDIO_ERROR")) { return 1; }
    *out = calloc(1, sizeof(**out));
    if (!*out) { return 1; }
    if (mika_pcm_init(&(*out)->pcm, MIKA_MAX_FRAMES)) { free(*out); *out = NULL; return 1; }
    mika_atomic_set(&(*out)->pcm.frames, getenv("MIKA_FIXTURE_LIMIT") ? MIKA_MAX_FRAMES : 16000);
    return 0;
}
int mika_audio_failed(MikaAudio *audio) { (void)audio; return getenv("MIKA_FIXTURE_DEVICE_LOST") != NULL; }
size_t mika_audio_frames(MikaAudio *audio) { return mika_atomic_get(&audio->pcm.frames); }
const float *mika_audio_samples(MikaAudio *audio) { return audio->pcm.samples; }
void mika_audio_stop(MikaAudio *audio) { (void)audio; }
void mika_audio_close(MikaAudio *audio)
{
    if (audio) { mika_pcm_free(&audio->pcm); free(audio); }
}

int mika_engine_open(const char *path, MikaCancelled cancelled, void *userdata, MikaEngine **out)
{
    (void)path;
    *out = calloc(1, sizeof(**out));
    if (!*out) { return 1; }
    (*out)->cancelled = cancelled;
    (*out)->userdata = userdata;
    return 0;
}
int mika_engine_run(MikaEngine *engine, const float *pcm, size_t frames, const char **text)
{
    (void)pcm; (void)frames;
    if (getenv("MIKA_FIXTURE_SLOW_INFERENCE")) {
        double deadline = mika_now() + 5.0;
        while (mika_now() < deadline) {
            if (engine->cancelled(engine->userdata)) { return 130; }
#ifdef _WIN32
            Sleep(10);
#else
            struct timespec pause = {0, 10000000};
            nanosleep(&pause, NULL);
#endif
        }
    }
    if (getenv("MIKA_FIXTURE_INFERENCE_ERROR")) { return 1; }
    const char *value = getenv("MIKA_FIXTURE_TEXT");
    if (!value) { value = "Test transcript."; }
    if (getenv("MIKA_FIXTURE_SILENCE")) { value = ""; }
    engine->text = malloc(strlen(value) + 1);
    if (!engine->text) { return 1; }
    strcpy(engine->text, value);
    *text = engine->text;
    return 0;
}
void mika_engine_close(MikaEngine *engine)
{
    if (engine) { free(engine->text); free(engine); }
}

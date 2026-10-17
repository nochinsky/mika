#include "engine.h"
#include "platform.h"
#include "transcribe.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

struct MikaEngine {
    struct transcribe_session *session;
    MikaCancelled cancelled;
    void *userdata;
};

static void engine_log(transcribe_log_level level, const char *message, void *userdata)
{
    (void)userdata;
    if (level == TRANSCRIBE_LOG_LEVEL_ERROR) {
        mika_status_clear();
        fputs(message, stderr);
    }
}

static bool engine_abort(void *userdata)
{
    MikaEngine *engine = userdata;
    return engine->cancelled && engine->cancelled(engine->userdata);
}

int mika_engine_open(const char *model_path, MikaCancelled cancelled, void *userdata,
                     MikaEngine **out)
{
    *out = NULL;
    MikaEngine *engine = calloc(1, sizeof(*engine));
    if (!engine) {
        mika_status_clear();
        fputs("mika: not enough memory to create an inference session.\n", stderr);
        return 1;
    }
    engine->cancelled = cancelled;
    engine->userdata = userdata;
    transcribe_log_set(engine_log, NULL);
    transcribe_status initialized = transcribe_init_backends_default();
    if (initialized != TRANSCRIBE_OK) {
        mika_status_clear();
        fprintf(stderr, "mika: cannot initialize packaged CPU backends: %s.\n",
                transcribe_status_string(initialized));
        free(engine);
        return 1;
    }
    struct transcribe_model_load_params load;
    transcribe_model_load_params_init(&load);
    load.backend = TRANSCRIBE_BACKEND_CPU;
    transcribe_status status = transcribe_open(model_path, &load, NULL, &engine->session);
    if (status != TRANSCRIBE_OK) {
        mika_status_clear();
        fprintf(stderr, "mika: cannot load model: %s.\n", transcribe_status_string(status));
        free(engine);
        return 1;
    }
    transcribe_set_abort_callback(engine->session, engine_abort, engine);
    *out = engine;
    return 0;
}

int mika_engine_run(MikaEngine *engine, const float *pcm, size_t frames,
                    const char **text)
{
    *text = NULL;
    if (engine_abort(engine)) {
        return 130;
    }
    if (!pcm || frames < 1600 || frames > INT_MAX) {
        mika_status_clear();
        fputs("mika: recording must contain at least 0.1 seconds of audio.\n", stderr);
        return 1;
    }
    struct transcribe_run_params params;
    transcribe_run_params_init(&params);
    params.language = "en";
    transcribe_status status = transcribe_run(engine->session, pcm, (int)frames, &params);
    if (engine_abort(engine) || status == TRANSCRIBE_ERR_ABORTED) {
        return 130; /* Never publish a partial transcript after cancellation. */
    }
    if (status != TRANSCRIBE_OK) {
        mika_status_clear();
        fprintf(stderr, "mika: transcription failed: %s.\n", transcribe_status_string(status));
        return 1;
    }
    *text = transcribe_full_text(engine->session);
    return 0;
}

void mika_engine_close(MikaEngine *engine)
{
    if (engine) {
        transcribe_session_free(engine->session);
        free(engine);
    }
}

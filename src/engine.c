#include "engine.h"
#include "assets.h"
#include "platform.h"
#include "speech_asset.h"
#include "verify.h"
#include "transcribe.h"
#include "transcribe/vad.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

struct MikaEngine {
    struct transcribe_session *session;
    struct transcribe_model *vad_model;
    struct transcribe_vad_session *vad;
    MikaCancelled cancelled;
    void *userdata;
    MikaEngineTimings timings;
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
    return mika_cancelled(NULL) || (engine->cancelled && engine->cancelled(engine->userdata));
}

static int engine_failure(transcribe_status status, const char *operation)
{
    mika_status_clear();
    fprintf(stderr, "mika: cannot %s: %s.\n", operation, transcribe_status_string((int)status));
    return 1;
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
    int result = 1;
    char *vad_path = NULL;
    if (engine_abort(engine)) { result = 130; goto failed; }
    transcribe_log_set(engine_log, NULL);
    transcribe_status status = transcribe_init_backends_default();
    if (status != TRANSCRIBE_OK) { engine_failure(status, "initialize packaged CPU backends"); goto failed; }
    vad_path = mika_asset_path("speech/" MIKA_VAD_FILE);
    int verified = vad_path ? mika_model_verify(vad_path, MIKA_VAD_BYTES, MIKA_VAD_SHA256) : MIKA_MODEL_IO_ERROR;
    if (verified == 130 || engine_abort(engine)) { result = 130; goto failed; }
    if (verified != MIKA_MODEL_VALID) {
        mika_status_clear();
        fputs("mika: speech-detection data is missing or damaged. Reinstall Mika; no transcript produced.\n", stderr);
        goto failed;
    }
    struct transcribe_model_load_params load;
    transcribe_model_load_params_init(&load);
    load.backend = TRANSCRIBE_BACKEND_CPU;
    status = transcribe_model_load_file(vad_path, &load, &engine->vad_model);
    if (status != TRANSCRIBE_OK) { engine_failure(status, "load speech detection"); goto failed; }
    struct transcribe_vad_session_params session;
    transcribe_vad_session_params_init(&session);
    session.n_threads = 1;
    status = transcribe_vad_session_init(engine->vad_model, &session, &engine->vad);
    if (status != TRANSCRIBE_OK) { engine_failure(status, "initialize speech detection"); goto failed; }
    transcribe_vad_set_abort_callback(engine->vad, engine_abort, engine);
    if (engine_abort(engine)) { result = 130; goto failed; }
    status = transcribe_open(model_path, &load, NULL, &engine->session);
    if (status != TRANSCRIBE_OK) { engine_failure(status, "load speech model"); goto failed; }
    transcribe_set_abort_callback(engine->session, engine_abort, engine);
    if (engine_abort(engine)) { result = 130; goto failed; }
    free(vad_path);
    *out = engine;
    return 0;
failed:
    free(vad_path);
    mika_engine_close(engine);
    return result;
}

int mika_engine_run(MikaEngine *engine, const float *pcm, size_t frames, const char **text)
{
    *text = NULL;
    engine->timings = (MikaEngineTimings){0};
    if (engine_abort(engine)) { return 130; }
    if (!pcm || frames < 1600 || frames > INT_MAX) {
        mika_status_clear();
        fputs("mika: recording must contain at least 0.1 seconds of audio.\n", stderr);
        return 1;
    }
    struct transcribe_vad_params gate;
    transcribe_vad_params_init(&gate);
    /* Admission only: retain brief words, never trim/concatenate speech segments
       or require speech to occupy a fraction of a longer recording. */
    gate.min_speech_ms = 0;
    double started = mika_now();
    transcribe_status status = transcribe_vad_run(engine->vad, pcm, (int)frames, &gate);
    engine->timings.speech_gate_ms = 1000.0 * (mika_now() - started);
    if (engine_abort(engine) || status == TRANSCRIBE_ERR_ABORTED) { return 130; }
    if (status != TRANSCRIBE_OK) { return engine_failure(status, "detect speech"); }
    struct transcribe_vad_result detected;
    transcribe_vad_result_init(&detected);
    status = transcribe_vad_get_result(engine->vad, &detected);
    if (status != TRANSCRIBE_OK) { return engine_failure(status, "read speech detection result"); }
    if (detected.n_segments < 0 || detected.n_probs <= 0 || detected.n_segments > detected.n_probs) {
        mika_status_clear();
        fputs("mika: invalid speech detection result; no transcript produced.\n", stderr);
        return 1;
    }
    if (engine_abort(engine)) { return 130; }
    if (!detected.n_segments) { return 3; }
    engine->timings.speech_admitted = 1;
    struct transcribe_run_params params;
    transcribe_run_params_init(&params);
    params.language = "en";
    started = mika_now();
    /* Preserve the original recording, including pauses and boundary consonants. */
    status = transcribe_run(engine->session, pcm, (int)frames, &params);
    engine->timings.inference_ms = 1000.0 * (mika_now() - started);
    if (engine_abort(engine) || status == TRANSCRIBE_ERR_ABORTED) { return 130; }
    if (status != TRANSCRIBE_OK) { return engine_failure(status, "transcribe recording"); }
    *text = transcribe_full_text(engine->session);
    return 0;
}

MikaEngineTimings mika_engine_timings(const MikaEngine *engine)
{
    return engine ? engine->timings : (MikaEngineTimings){0};
}

void mika_engine_close(MikaEngine *engine)
{
    if (engine) {
        transcribe_session_free(engine->session);
        transcribe_vad_session_free(engine->vad);
        transcribe_model_free(engine->vad_model);
        free(engine);
    }
}

/* Real engine.c with fake ML/filesystem adapters. No weights, audio or network. */
#include "engine.h"
#include "assets.h"
#include "speech_asset.h"
#include "verify.h"
#include "transcribe.h"
#include "transcribe/vad.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct transcribe_session { int unused; };
struct transcribe_model { int unused; };
struct transcribe_vad_session { int unused; };
static struct transcribe_session asr;
static struct transcribe_model model;
static struct transcribe_vad_session vad;
static int fail_stage, cancelled, segments, malformed, cancel_in_vad, cancel_after_result;
static int asr_runs, vad_runs, model_loaded, vad_loaded, asr_loaded;
static int model_freed, vad_freed, asr_freed;
static const float *original;
static transcribe_abort_callback gate_abort;
static void *gate_userdata;

static void reset(void)
{
    fail_stage = cancelled = malformed = cancel_in_vad = cancel_after_result = 0;
    asr_runs = vad_runs = model_loaded = vad_loaded = asr_loaded = 0;
    model_freed = vad_freed = asr_freed = 0;
    segments = 1;
}
static int stop(void *unused) { (void)unused; return cancelled; }
char *mika_asset_path(const char *relative)
{
    assert(strcmp(relative, "speech/" MIKA_VAD_FILE) == 0);
    if (fail_stage == 2) { return NULL; }
    char *path = malloc(8);
    assert(path);
    memcpy(path, "vad.bin", 8);
    return path;
}
int mika_model_verify(const char *path, uint64_t bytes, const char *hash)
{
    assert(strcmp(path, "vad.bin") == 0 && bytes == MIKA_VAD_BYTES && strcmp(hash, MIKA_VAD_SHA256) == 0);
    return fail_stage == 3 ? MIKA_MODEL_INVALID : fail_stage == 4 ? 130 : MIKA_MODEL_VALID;
}
void transcribe_log_set(void (*callback)(transcribe_log_level, const char *, void *), void *data) { (void)callback; (void)data; }
transcribe_status transcribe_init_backends_default(void) { return fail_stage == 1 ? TRANSCRIBE_ERR_INVALID_ARG : TRANSCRIBE_OK; }
const char *transcribe_status_string(int status) { (void)status; return "test status"; }
void transcribe_model_load_params_init(struct transcribe_model_load_params *p) { memset(p, 0, sizeof(*p)); }
transcribe_status transcribe_model_load_file(const char *path, const struct transcribe_model_load_params *p, struct transcribe_model **out)
{
    assert(strcmp(path, "vad.bin") == 0 && p->backend == TRANSCRIBE_BACKEND_CPU);
    if (fail_stage == 5) { return TRANSCRIBE_ERR_INVALID_ARG; }
    *out = &model; ++model_loaded; return TRANSCRIBE_OK;
}
void transcribe_model_free(struct transcribe_model *p)
{
    if (p) { assert(p == &model && vad_freed == vad_loaded); ++model_freed; }
}
void transcribe_vad_session_params_init(struct transcribe_vad_session_params *p) { memset(p, 0, sizeof(*p)); }
transcribe_status transcribe_vad_session_init(struct transcribe_model *m, const struct transcribe_vad_session_params *p, struct transcribe_vad_session **out)
{
    assert(m == &model && p->n_threads == 1);
    if (fail_stage == 6) { return TRANSCRIBE_ERR_INVALID_ARG; }
    *out = &vad; ++vad_loaded; return TRANSCRIBE_OK;
}
void transcribe_vad_session_free(struct transcribe_vad_session *p) { if (p) { assert(p == &vad); ++vad_freed; } }
void transcribe_vad_set_abort_callback(struct transcribe_vad_session *p, transcribe_abort_callback callback, void *data)
{
    assert(p == &vad); gate_abort = callback; gate_userdata = data;
}
transcribe_status transcribe_open(const char *path, const struct transcribe_model_load_params *load, const struct transcribe_session_params *p, struct transcribe_session **out)
{
    (void)p; assert(strcmp(path, "asr.gguf") == 0 && load->backend == TRANSCRIBE_BACKEND_CPU);
    if (fail_stage == 7) { return TRANSCRIBE_ERR_INVALID_ARG; }
    *out = &asr; ++asr_loaded; return TRANSCRIBE_OK;
}
void transcribe_session_free(struct transcribe_session *p) { if (p) { assert(p == &asr); ++asr_freed; } }
void transcribe_set_abort_callback(struct transcribe_session *p, transcribe_abort_callback cb, void *data)
{
    assert(p == &asr && cb == gate_abort && data == gate_userdata);
}
void transcribe_vad_params_init(struct transcribe_vad_params *p) { p->threshold = .5; p->min_speech_ms = 250; }
void transcribe_vad_result_init(struct transcribe_vad_result *p) { memset(p, 0, sizeof(*p)); }
transcribe_status transcribe_vad_run(struct transcribe_vad_session *p, const float *pcm, int frames, const struct transcribe_vad_params *params)
{
    assert(p == &vad && pcm == original && frames == 1600 && params->min_speech_ms == 0 && params->threshold == .5);
    ++vad_runs;
    if (cancel_in_vad) { cancelled = 1; assert(gate_abort(gate_userdata)); return TRANSCRIBE_ERR_ABORTED; }
    return fail_stage == 8 ? TRANSCRIBE_ERR_INVALID_ARG : TRANSCRIBE_OK;
}
transcribe_status transcribe_vad_get_result(const struct transcribe_vad_session *p, struct transcribe_vad_result *out)
{
    assert(p == &vad); out->n_segments = segments; out->n_probs = malformed ? 0 : 4;
    if (cancel_after_result) { cancelled = 1; }
    return fail_stage == 9 ? TRANSCRIBE_ERR_INVALID_ARG : TRANSCRIBE_OK;
}
void transcribe_run_params_init(struct transcribe_run_params *p) { memset(p, 0, sizeof(*p)); }
transcribe_status transcribe_run(struct transcribe_session *p, const float *pcm, int frames, const struct transcribe_run_params *params)
{
    assert(p == &asr && pcm == original && frames == 1600 && strcmp(params->language, "en") == 0);
    ++asr_runs; return fail_stage == 10 ? TRANSCRIBE_ERR_INVALID_ARG : TRANSCRIBE_OK;
}
const char *transcribe_full_text(struct transcribe_session *p) { assert(p == &asr); return "thank you"; }
static void closed(MikaEngine *engine)
{
    mika_engine_close(engine);
    assert(asr_loaded == asr_freed && vad_loaded == vad_freed && model_loaded == model_freed);
}

int main(void)
{
    float pcm[1600] = {0};
    original = pcm;
    for (int stage = 1; stage <= 7; ++stage) {
        reset(); fail_stage = stage;
        MikaEngine *engine = NULL;
        assert(mika_engine_open("asr.gguf", stop, NULL, &engine) == (stage == 4 ? 130 : 1));
        assert(!engine); closed(engine);
    }
    reset(); cancelled = 1;
    MikaEngine *engine = NULL;
    assert(mika_engine_open("asr.gguf", stop, NULL, &engine) == 130 && !engine);
    reset(); assert(mika_engine_open("asr.gguf", stop, NULL, &engine) == 0);
    const char *text = NULL;
    assert(mika_engine_run(engine, pcm, 1600, &text) == 0 && strcmp(text, "thank you") == 0);
    assert(asr_runs == 1 && vad_runs == 1 && mika_engine_timings(engine).speech_admitted == 1);
    segments = 0; text = "stale";
    assert(mika_engine_run(engine, pcm, 1600, &text) == 3 && !text && asr_runs == 1);
    assert(mika_engine_timings(engine).inference_ms == 0 && !mika_engine_timings(engine).speech_admitted);
    segments = 1;
    for (int stage = 8; stage <= 10; ++stage) {
        fail_stage = stage; text = "stale";
        assert(mika_engine_run(engine, pcm, 1600, &text) == 1 && !text);
    }
    fail_stage = 0; malformed = 1;
    assert(mika_engine_run(engine, pcm, 1600, &text) == 1 && !text);
    malformed = 0; segments = -1;
    assert(mika_engine_run(engine, pcm, 1600, &text) == 1 && !text);
    segments = 1; cancel_in_vad = 1;
    assert(mika_engine_run(engine, pcm, 1600, &text) == 130 && !text);
    cancelled = cancel_in_vad = 0; cancel_after_result = 1;
    int previous_asr = asr_runs;
    assert(mika_engine_run(engine, pcm, 1600, &text) == 130 && !text && asr_runs == previous_asr);
    cancelled = cancel_after_result = 0;
    int previous_vad = vad_runs;
    assert(mika_engine_run(engine, NULL, 1600, &text) == 1);
    assert(mika_engine_run(engine, pcm, 1599, &text) == 1);
    assert(mika_engine_run(engine, pcm, (size_t)INT_MAX + 1u, &text) == 1);
    assert(vad_runs == previous_vad);
    closed(engine);
    puts("PASS: mandatory CPU gate, failure cleanup, no-speech, cancellation, original PCM, repeated-run reset and admission boundaries");
    return 0;
}

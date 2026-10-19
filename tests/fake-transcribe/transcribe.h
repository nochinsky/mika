/* Minimal test-only API surface for compiling the real engine without ML.
 * Production always uses the pinned upstream headers/library; full/native builds
 * additionally validate that ABI. These fakes exercise Mika's admission policy. */
#ifndef MIKA_TEST_TRANSCRIBE_H
#define MIKA_TEST_TRANSCRIBE_H
#include <stdbool.h>
#include <stdint.h>

typedef enum { TRANSCRIBE_OK, TRANSCRIBE_ERR_INVALID_ARG, TRANSCRIBE_ERR_ABORTED } transcribe_status;
typedef enum { TRANSCRIBE_LOG_LEVEL_ERROR } transcribe_log_level;
enum { TRANSCRIBE_BACKEND_CPU = 1 };
typedef bool (*transcribe_abort_callback)(void *);
struct transcribe_session;
struct transcribe_model;
struct transcribe_session_params;
struct transcribe_model_load_params { int backend; };
struct transcribe_run_params { const char *language; };
void transcribe_log_set(void (*callback)(transcribe_log_level, const char *, void *), void *userdata);
transcribe_status transcribe_init_backends_default(void);
const char *transcribe_status_string(int status);
void transcribe_model_load_params_init(struct transcribe_model_load_params *params);
transcribe_status transcribe_model_load_file(const char *path, const struct transcribe_model_load_params *params, struct transcribe_model **model);
void transcribe_model_free(struct transcribe_model *model);
transcribe_status transcribe_open(const char *path, const struct transcribe_model_load_params *load, const struct transcribe_session_params *params, struct transcribe_session **session);
void transcribe_session_free(struct transcribe_session *session);
void transcribe_set_abort_callback(struct transcribe_session *session, transcribe_abort_callback callback, void *userdata);
void transcribe_run_params_init(struct transcribe_run_params *params);
transcribe_status transcribe_run(struct transcribe_session *session, const float *pcm, int frames, const struct transcribe_run_params *params);
const char *transcribe_full_text(struct transcribe_session *session);
#endif

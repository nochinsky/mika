#ifndef MIKA_TEST_VAD_H
#define MIKA_TEST_VAD_H
#include "transcribe.h"
struct transcribe_vad_session;
struct transcribe_vad_session_params { int n_threads; };
struct transcribe_vad_params { double threshold; int min_speech_ms; };
struct transcribe_vad_result { int n_probs, n_segments; };
void transcribe_vad_session_params_init(struct transcribe_vad_session_params *params);
void transcribe_vad_params_init(struct transcribe_vad_params *params);
void transcribe_vad_result_init(struct transcribe_vad_result *result);
transcribe_status transcribe_vad_session_init(struct transcribe_model *model, const struct transcribe_vad_session_params *params, struct transcribe_vad_session **session);
void transcribe_vad_session_free(struct transcribe_vad_session *session);
void transcribe_vad_set_abort_callback(struct transcribe_vad_session *session, transcribe_abort_callback callback, void *userdata);
transcribe_status transcribe_vad_run(struct transcribe_vad_session *session, const float *pcm, int frames, const struct transcribe_vad_params *params);
transcribe_status transcribe_vad_get_result(const struct transcribe_vad_session *session, struct transcribe_vad_result *result);
#endif

/* Explicit, opt-in real-model probe. Never records microphone audio. */
#include "engine.h"
#include "miniaudio.h"
#include "platform.h"
#include "model.h"
#include "punctuation.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include "peak_rss.h"

int main(int argc, char **argv)
{
    int raw_mode = argc == 4 && strcmp(argv[3], "--raw") == 0;
    if (argc != 3 && !raw_mode) {
        fputs("usage: mika-inference-test MODEL.gguf SAMPLE.wav [--raw]\n", stderr);
        return 2;
    }
    if (mika_platform_init()) { return 1; }
    double pipeline_start = mika_now();
    int verified = mika_model_verify(argv[1], MIKA_MODEL_BYTES, MIKA_MODEL_SHA256);
    double verified_at = mika_now();
    if (verified) {
        fputs("Cannot verify speech model.\n", stderr);
        return verified == 130 ? 130 : 1;
    }
    ma_decoder_config config = ma_decoder_config_init(ma_format_f32, 1, 16000);
    ma_uint64 frames = 0;
    void *pcm = NULL;
    if (ma_decode_file(argv[2], &config, &frames, &pcm) != MA_SUCCESS) {
        fputs("Cannot decode sample.\n", stderr);
        return 1;
    }
    MikaEngine *engine = NULL;
    double start = mika_now();
    int result = mika_engine_open(argv[1], NULL, NULL, &engine);
    double loaded = mika_now();
    const char *text = NULL;
    if (!result) {
        result = mika_engine_run(engine, pcm, (size_t)frames, &text);
    }
    double inferred = mika_now();
    MikaEngineTimings timings = mika_engine_timings(engine);
    fprintf(stderr, "speech_gate_ms=%.3f asr_ms=%.3f speech_admitted=%d\n",
            timings.speech_gate_ms, timings.inference_ms, timings.speech_admitted);
    char *raw = NULL, *formatted = NULL;
    if (!result && (!text || !text[strspn(text, " \t\r\n\v\f")])) { result = 3; }
    if (!result && !raw_mode && text && mika_punctuation_input_valid(text)) {
        raw = malloc(strlen(text) + 1);
        /* Match the CLI: copy-allocation failure keeps valid borrowed raw text,
           rather than turning a recoverable formatting failure into ASR loss. */
        if (raw) {
            strcpy(raw, text);
            mika_engine_close(engine);
            engine = NULL;
            ma_free(pcm, NULL);
            pcm = NULL;
            double formatting_start = mika_now();
            int formatting = mika_punctuation_run(NULL, raw, NULL, NULL, &formatted, NULL, NULL);
            fprintf(stderr, "formatting=%d format_ms=%.3f\n", formatting,
                    1000.0 * (mika_now() - formatting_start));
            text = formatted ? formatted : raw;
            if (formatting == 130) { result = 130; }
        }
    }
    if (!result) {
        if (puts(text ? text : "") == EOF || fflush(stdout) != 0) { result = 1; }
        fprintf(stderr, "audio=%.2fs load=%.3fs inference=%.3fs verify_ms=%.3f model_ready_ms=%.3f\n",
                (double)frames / 16000.0, loaded - start, inferred - loaded,
                (verified_at - pipeline_start) * 1000.0,
                ((verified_at - pipeline_start) + (loaded - start)) * 1000.0);
    }
    mika_engine_close(engine);
    ma_free(pcm, NULL);
    free(formatted);
    free(raw);
    fprintf(stderr, "pipeline_ms=%.3f peak_rss_kib=%" PRIu64 "\n",
            (mika_now() - pipeline_start) * 1000.0, peak_rss_kib());
    return result;
}

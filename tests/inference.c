/* Explicit, opt-in real-model probe. Never records microphone audio. */
#include "engine.h"
#include "miniaudio.h"
#include "platform.h"
#ifdef MIKA_EXPERIMENTAL_PUNCTUATION
#include "punctuation.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
#ifdef MIKA_EXPERIMENTAL_PUNCTUATION
    int punctuate = argc == 4 && strcmp(argv[3], "--punctuate") == 0;
    if (argc != 3 && !punctuate) {
#else
    if (argc != 3) {
#endif
        fputs("usage: mika-inference-test MODEL.gguf SAMPLE.wav\n", stderr);
        return 2;
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
#ifdef MIKA_EXPERIMENTAL_PUNCTUATION
    char *raw = NULL, *formatted = NULL;
    if (!result && punctuate && text) {
        raw = malloc(strlen(text) + 1);
        if (!raw) { result = 1; }
        else {
            strcpy(raw, text);
            mika_engine_close(engine);
            engine = NULL;
            ma_free(pcm, NULL);
            pcm = NULL;
            double formatting_start = mika_now();
            int formatting = mika_punctuation_run(NULL, raw, NULL, NULL, &formatted);
            fprintf(stderr, "formatting=%d format_ms=%.3f\n", formatting,
                    1000.0 * (mika_now() - formatting_start));
            text = formatted ? formatted : raw;
            if (formatting == 130) { result = 130; }
        }
    }
#endif
    if (!result) {
        if (puts(text ? text : "") == EOF || fflush(stdout) != 0) { result = 1; }
        fprintf(stderr, "audio=%.2fs load=%.3fs inference=%.3fs\n",
                (double)frames / 16000.0, loaded - start, inferred - loaded);
    }
    mika_engine_close(engine);
    ma_free(pcm, NULL);
#ifdef MIKA_EXPERIMENTAL_PUNCTUATION
    free(formatted);
    free(raw);
#endif
    return result;
}

/* Explicit, opt-in real-model probe. Never records microphone audio. */
#include "engine.h"
#include "miniaudio.h"
#include "platform.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    if (argc != 3) {
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
    if (!result) {
        puts(text ? text : "");
        fprintf(stderr, "audio=%.2fs load=%.3fs inference=%.3fs\n",
                (double)frames / 16000.0, loaded - start, mika_now() - loaded);
    }
    mika_engine_close(engine);
    ma_free(pcm, NULL);
    return result;
}

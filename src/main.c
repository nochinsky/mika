#include "audio.h"
#include "engine.h"
#include "model.h"
#include "pcm.h"
#include "platform.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef MIKA_VERSION
#define MIKA_VERSION "0.1.0"
#endif

static void help(void)
{
    fputs("Mika " MIKA_VERSION " - offline English speech to text\n\n"
          "Usage: mika [--help | --version]\n\n"
          "Run mika, speak after 'Listening', then press Enter to transcribe.\n"
          "Esc or Ctrl+C cancels without printing a transcript.\n"
          "The default system microphone is used; select it in your OS sound settings.\n"
          "Recordings are kept in memory, capped at 60 seconds, and never saved.\n"
          "At the limit Mika stops recording and transcribes automatically.\n\n"
          "The first run asks permission to download the fixed 279 MB English model.\n"
          "Later runs work offline. No account, setup command, or clipboard access.\n"
          "Only the transcript goes to stdout; status messages go to stderr.\n"
          "Example: mika > notes.txt\n\n"
          "Model: " MIKA_MODEL_FILE "\n", stdout);
    char *directory = mika_model_directory();
    if (directory) { printf("Model directory: %s\n", directory); free(directory); }
}

struct Cancellation { MikaTerminal *terminal; int requested; };

static int cancel_requested(void *userdata)
{
    struct Cancellation *cancel = userdata;
    if (mika_cancelled(NULL)) { cancel->requested = 1; }
    /* Also consume keys queued while loading or doing synchronous inference. */
    for (unsigned i = 0; i < 128 && !cancel->requested; ++i) {
        int key = mika_terminal_key(cancel->terminal, 0);
        if (key == MIKA_KEY_TIMEOUT) { break; }
        if (key == 27 || key == 3 || key == MIKA_KEY_ERROR) { cancel->requested = 1; }
    }
    return cancel->requested;
}

int main(int argc, char **argv)
{
    mika_console_utf8();
    if (argc == 2 && (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0)) {
        help();
        return fflush(stdout) != 0 || ferror(stdout) ? 1 : 0;
    }
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts("mika " MIKA_VERSION);
        return fflush(stdout) != 0 || ferror(stdout) ? 1 : 0;
    }
    if (argc != 1) {
        fputs("mika: unexpected argument. Run 'mika --help' for usage.\n", stderr);
        return 2;
    }
    if (mika_platform_init() != 0) {
        fputs("mika: cannot initialize cancellation handling.\n", stderr);
        return 1;
    }
    MikaTerminal *terminal = mika_terminal_open();
    if (!terminal) {
        fputs("mika: no controlling terminal. Run Mika from an interactive terminal.\n"
              "      Redirecting stdout (mika > notes.txt) is supported.\n", stderr);
        return 1;
    }
    struct Cancellation cancel = {terminal, 0};
    MikaEngine *engine = NULL;
    MikaAudio *audio = NULL;
    char *model_path = NULL;
    const char *text = NULL;
    int animated = mika_stderr_is_terminal();
    int result = 1;
    mika_terminal_discard_input(terminal);
    fputs("\n  mika\n", stderr);
    result = mika_model_ensure(terminal, &model_path);
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = 130; goto done; }
    fputs("  Loading model (CPU)...\n", stderr);
    result = mika_engine_open(model_path, cancel_requested, &cancel, &engine);
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = 130; goto done; }
    fputs("  Opening microphone...\n", stderr);
    result = mika_audio_start(&audio);
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = 130; goto done; }
    fputs("  Listening - Enter to transcribe, Esc to cancel (60-second limit).\n", stderr);
    double last_audio = mika_now();
    size_t previous_frames = 0;
    unsigned previous_second = UINT32_MAX;
    for (;;) {
        if (mika_cancelled(NULL)) { result = 130; break; }
        if (mika_audio_failed(audio)) {
            fputs("\nmika: microphone capture stopped unexpectedly.\n", stderr);
            result = 1;
            break;
        }
        size_t frames = mika_audio_frames(audio);
        unsigned seconds = (unsigned)(frames / MIKA_SAMPLE_RATE);
        if (animated && seconds != previous_second) {
            fprintf(stderr, "\r  Listening %02u:%02u - Enter: transcribe | Esc: cancel   ", seconds / 60, seconds % 60);
            fflush(stderr);
            previous_second = seconds;
        }
        if (frames != previous_frames) { last_audio = mika_now(); previous_frames = frames; }
        if (mika_now() - last_audio > 5.0) {
            fputs("\nmika: no audio is arriving from the microphone. Check your system input.\n", stderr);
            result = 1;
            break;
        }
        if (frames >= MIKA_MAX_FRAMES) {
            fputs("\n  60-second limit reached; finishing recording.\n", stderr);
            result = 0;
            break;
        }
        int key = mika_terminal_key(terminal, 100);
        if (key == '\n') { result = 0; break; }
        if (key == 27 || key == 3) { result = 130; break; }
        if (key == MIKA_KEY_ERROR) {
            fputs("\nmika: lost the controlling terminal.\n", stderr);
            result = 1;
            break;
        }
    }
    mika_audio_stop(audio);
    if (animated) { fputc('\n', stderr); }
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = 130; goto done; }
    if (mika_audio_failed(audio)) {
        fputs("mika: microphone capture failed; no transcript produced.\n", stderr);
        result = 1;
        goto done;
    }
    fputs("  Transcribing (CPU)...\n", stderr);
    result = mika_engine_run(engine, mika_audio_samples(audio), mika_audio_frames(audio), &text);
    if (cancel_requested(&cancel)) { result = 130; }
done:
    mika_audio_close(audio);
    /* Restore the terminal BEFORE output: a broken stdout pipe must not leave raw mode. */
    mika_terminal_close(terminal);
    free(model_path);
    if (mika_cancelled(NULL)) { result = 130; }
    if (result == 130) { fputs("\n  Cancelled.\n", stderr); }
    if (!result) {
        if (!text || !text[0]) { fputs("  No speech recognized.\n", stderr); }
        if (puts(text ? text : "") == EOF || fflush(stdout) != 0) {
            fputs("mika: cannot write the transcript to stdout.\n", stderr);
            result = 1;
        }
    }
    mika_engine_close(engine);
    return result;
}

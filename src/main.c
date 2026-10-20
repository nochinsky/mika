#include "audio.h"
#include "engine.h"
#include "model.h"
#include "pcm.h"
#include "platform.h"
#include "punctuation.h"
#include "mika_version.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void help(void)
{
    fputs("Mika " MIKA_VERSION " - offline English speech to text\n\n"
          "Usage: mika [--raw | --help | --version]\n\n"
          "Run mika, speak after 'Listening', then press Enter to transcribe.\n"
          "Esc or Ctrl+C cancels without printing a transcript.\n"
          "The default system microphone is used; select it in your OS sound settings.\n", stdout);
    printf("Recordings are kept in memory, capped at %u minutes, and never saved.\n",
           MIKA_MAX_SECONDS / 60u);
    fputs("At the limit Mika stops recording and transcribes automatically.\n\n"
          "The first run asks permission to download the fixed 279 MB English model.\n"
          "Later runs work offline. No account, setup command, or clipboard access.\n"
          "Only the transcript goes to stdout; status messages go to stderr.\n"
          "Example: mika > notes.txt\n\n"
          "Model: " MIKA_MODEL_FILE "\n", stdout);
    fputs("\nOffline punctuation/casing is on by default. --raw skips formatting.\n"
          "Formatting may be wrong; failures keep the original transcript.\n"
          "Exit codes: 0 transcript, 1 failure, 2 arguments, 3 no speech, 130 cancelled.\n", stdout);
    char *directory = mika_model_directory();
    if (directory) { printf("Model directory: %s\n", directory); free(directory); }
}

/* Preserve why work stopped: terminal failure is not user cancellation. */
struct Cancellation { MikaTerminal *terminal; int result; };

static int cancel_requested(void *userdata)
{
    struct Cancellation *cancel = userdata;
    if (mika_cancelled(NULL)) { cancel->result = 130; }
    /* Also consume keys queued while loading or doing synchronous inference. */
    for (unsigned i = 0; i < 128 && !cancel->result; ++i) {
        int key = mika_terminal_key(cancel->terminal, 0);
        if (key == MIKA_KEY_TIMEOUT) { break; }
        if (key == 27 || key == 3) { cancel->result = 130; }
        if (key == MIKA_KEY_ERROR) { cancel->result = 1; }
    }
    return cancel->result != 0;
}

/* Capture is already running. The caller stops it before consuming final PCM. */
static int record_until_finished(MikaAudio *audio, struct Cancellation *cancel, int *limit_reached)
{
    *limit_reached = 0;
    double last_audio = mika_now();
    size_t previous_frames = 0;
    unsigned previous_second = UINT32_MAX;
    for (;;) {
        if (mika_cancelled(NULL)) { return 130; }
        if (mika_audio_failed(audio)) {
            mika_status_clear();
            fputs("mika: microphone capture stopped unexpectedly.\n", stderr);
            return 1;
        }
        size_t frames = mika_audio_frames(audio);
        unsigned seconds = (unsigned)(frames / MIKA_SAMPLE_RATE);
        if (seconds != previous_second) {
            char status[96];
            snprintf(status, sizeof(status), "Listening %02u:%02u / %02u:%02u   Enter: finish | Esc: cancel",
                     seconds / 60, seconds % 60, MIKA_MAX_SECONDS / 60u, MIKA_MAX_SECONDS % 60u);
            mika_status_show(status);
            previous_second = seconds;
        }
        if (frames != previous_frames) { last_audio = mika_now(); previous_frames = frames; }
        if (mika_now() - last_audio > 5.0) {
            mika_status_clear();
            fputs("mika: no audio is arriving from the microphone. Check your system input.\n", stderr);
            return 1;
        }
        if (frames >= MIKA_MAX_FRAMES) { *limit_reached = 1; return 0; }
        int key = mika_terminal_key(cancel->terminal, 100);
        if (key == '\n') { return 0; }
        if (key == 27 || key == 3) { return 130; }
        if (key == MIKA_KEY_ERROR) { cancel->result = 1; return 1; }
    }
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
    int raw = argc == 2 && strcmp(argv[1], "--raw") == 0;
    if (argc != 1 && !raw) {
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
    char *raw_copy = NULL, *formatted = NULL;
    int result = 1;
    int limit_reached = 0;
    mika_terminal_discard_input(terminal);
    mika_status_show("Starting...");
    result = mika_model_ensure(terminal, &model_path);
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = cancel.result; goto done; }
    mika_status_show("Starting...");
    result = mika_engine_open(model_path, cancel_requested, &cancel, &engine);
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = cancel.result; goto done; }
    result = mika_audio_start(&audio);
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = cancel.result; goto done; }
    result = record_until_finished(audio, &cancel, &limit_reached);
    mika_audio_stop(audio);
    if (result) { goto done; }
    if (cancel_requested(&cancel)) { result = cancel.result; goto done; }
    if (mika_audio_failed(audio)) {
        mika_status_clear();
        fputs("mika: microphone capture failed; no transcript produced.\n", stderr);
        result = 1;
        goto done;
    }
    if (limit_reached) {
        char status[80];
        snprintf(status, sizeof(status), "Transcribing (%u-minute limit reached)...", MIKA_MAX_SECONDS / 60u);
        mika_status_show(status);
    } else {
        mika_status_show("Transcribing...");
    }
    result = mika_engine_run(engine, mika_audio_samples(audio), mika_audio_frames(audio), &text);
    if (cancel_requested(&cancel)) { result = cancel.result; }
    if (!result && !raw && text && text[strspn(text, " \t\r\n\v\f")]) {
        int formatting = 1;
        MikaPunctuationFailure failure = MIKA_PUNCTUATION_INPUT;
        MikaPunctuationDiagnostic diagnostic = {{0}};
        if (mika_punctuation_input_valid(text)) {
            size_t bytes = strlen(text) + 1;
            raw_copy = malloc(bytes);
            failure = MIKA_PUNCTUATION_MEMORY;
            if (raw_copy) {
                memcpy(raw_copy, text, bytes);
                text = raw_copy;
                /* Do not hold speech weights/recording memory while loading ORT. */
                mika_engine_close(engine);
                engine = NULL;
                mika_audio_close(audio);
                audio = NULL;
                mika_status_show("Formatting...");
                formatting = mika_punctuation_run(NULL, text, cancel_requested, &cancel, &formatted, &failure, &diagnostic);
            }
        }
        if (!formatting) { text = formatted; }
        else if (formatting == 130) { result = 130; }
        else {
            mika_status_clear();
            fprintf(stderr, "mika: %s; keeping the raw transcript.\n",
                    mika_punctuation_failure_message(failure));
            if (failure == MIKA_PUNCTUATION_RUNTIME && diagnostic.message[0]) {
                fprintf(stderr, "mika: %s\n", diagnostic.message);
#ifdef __APPLE__
                fputs("mika: for an unidentified-developer block, see Mac first-run approval: "
                      "https://github.com/nochinsky/mika/blob/main/docs/macos.md#first-run-security-approval\n", stderr);
#endif
            }
        }
        if (cancel_requested(&cancel)) { result = cancel.result; }
    }
done:
    mika_audio_close(audio);
    mika_status_clear();
    /* Restore the terminal before publishing output or final diagnostics. */
    mika_terminal_close(terminal);
    free(model_path);
    if (mika_cancelled(NULL)) { result = 130; }
    else if (cancel.result) { result = cancel.result; }
    if (result == 1 && cancel.result == 1) { fputs("mika: lost the controlling terminal.\n", stderr); }
    if (result == 130) { fputs("Cancelled.\n", stderr); }
    if (!result && (!text || !text[strspn(text, " \t\r\n\v\f")])) { result = 3; }
    if (result == 3) { fputs("No speech recognized.\n", stderr); }
    if (!result) {
        if (puts(text) == EOF || fflush(stdout) != 0) {
            fputs("mika: cannot write the transcript to stdout.\n", stderr);
            result = 1;
        }
    }
    mika_engine_close(engine);
    free(formatted);
    free(raw_copy);
    return result;
}

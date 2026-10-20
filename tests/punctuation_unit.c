#include "punctuation.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); return 1; } } while (0)

int main(void)
{
    struct { unsigned char before; MikaPunctuationDiagnostic value; unsigned char after; } diagnostic;
    memset(&diagnostic, 0xa5, sizeof(diagnostic));
    mika_punctuation_loader_diagnostic(NULL, NULL, NULL, NULL, 0);
    mika_punctuation_loader_diagnostic(&diagnostic.value, "onnxruntime.dll", NULL, NULL, 126);
    CHECK(!strcmp(diagnostic.value.message, "cannot load formatter library onnxruntime.dll (Windows error 126)"));
    mika_punctuation_loader_diagnostic(&diagnostic.value, "backend", "MikaFullstopOpen", "missing symbol", 0);
    CHECK(!strcmp(diagnostic.value.message, "cannot resolve MikaFullstopOpen in formatter library backend: missing symbol"));
    mika_punctuation_loader_diagnostic(&diagnostic.value, "backend", NULL, "bad\x1b[31m\r\n\t\x7f\xc3\xa9", 0);
    CHECK(strstr(diagnostic.value.message, "bad\\x1b[31m\\x0d\\x0a\\x09\\x7f\\xc3\\xa9"));
    char native_error[4096];
    memset(native_error, 'x', sizeof(native_error) - 1);
    native_error[sizeof(native_error) - 1] = 0;
    mika_punctuation_loader_diagnostic(&diagnostic.value, "backend", NULL, native_error, 0);
    size_t diagnostic_length = strlen(diagnostic.value.message);
    CHECK(diagnostic_length < sizeof(diagnostic.value.message));
    CHECK(!strcmp(diagnostic.value.message + diagnostic_length - 3, "..."));
    CHECK(diagnostic.before == 0xa5 && diagnostic.after == 0xa5);
    for (unsigned byte = 1; byte < 256; ++byte) {
        native_error[0] = (char)byte; native_error[1] = 0;
        mika_punctuation_loader_diagnostic(&diagnostic.value, "backend", NULL, native_error, 0);
        for (const unsigned char *p = (const unsigned char *)diagnostic.value.message; *p; ++p) {
            CHECK(*p >= 32 && *p < 127);
        }
    }
    const char *good[][2] = {
        {"", ""}, {" \t\n", ""}, {"hello world", "Hello, world."},
        {"are you ready", "Are you ready?"}, {"ibm", "IBM"},
        {"i don't know", "I don't know."}, {"version 0.1.2", "Version 0.1.2"},
        {"hello.", "Hello."}, {"why?", "Why?"}, {"co-op work", "Co-op work."},
        {"  one\ttwo\nthree ", "One, two, three."},
        {"a b c", "A, B. C?"}, {"wow!", "Wow!"},
        {"src/main.c", "src/main.c."}, {"mika_audio_stop", "mika_audio_stop."},
        {"jane@example.com", "jane@example.com"}, {"c++ c#", "c++ c#."},
        {"hello...", "Hello..."}, {"version1", "version1."},
        {"fooBar API MikaEngine", "fooBar, API MikaEngine."},
    };
    const char *bad[][2] = {
        {"hello world", "Hello there world."}, {"hello world", "Hello."},
        {"hello world", "World hello."}, {"i can't", "I can."},
        {"i can't", "I cant."}, {"we will", "We'll."}, {"one two", "Onetwo."},
        {"hello", "Hello!"}, {"hello", "Hello..."}, {"hello", "Hello,?"},
        {"hello.", "Hello"}, {"hello.", "Hello.."}, {"hello?", "Hello?."},
        {"hello", ".Hello"}, {"co-op", "Coop"}, {"foo", "F.oo"},
        {"1 2 3", "1 3 2"}, {"hello", "Hello\x1b[31m"}, {"hello", "Hello\x7f"},
        {"hello", "Hello\xc2\xa0"}, {"", "Invented"}, {"word", ""},
        {"src/main.c", "SRC/main.c"}, {"mika_audio_stop", "Mika_audio_stop"},
        {"jane@example.com", "Jane@example.COM"}, {"c++", "C++"},
        {"--verbose", "--Verbose"}, {"version1", "Version1"},
        {"fooBar", "Foobar"}, {"API", "Api"}, {"MikaEngine", "Mikaengine"},
    };
    for (size_t i = 0; i < sizeof(good)/sizeof(good[0]); ++i) {
        CHECK(mika_punctuation_preserves_words(good[i][0], good[i][1]));
        CHECK(mika_punctuation_output_safe(good[i][0], good[i][1]));
    }
    for (size_t i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) {
        CHECK(!mika_punctuation_preserves_words(bad[i][0], bad[i][1]));
        CHECK(!mika_punctuation_output_safe(bad[i][0], bad[i][1]));
    }
    const char *unsafe_boundaries[][2] = {
        {"do not execute cleanup", "Do not execute. Cleanup."},
        {"not now inspect first", "Not. Now inspect first."},
        {"never delete backups", "Never delete? Backups."},
        {"do NOT, execute cleanup", "Do NOT, execute. Cleanup."},
        {"don't remove backups", "Don't remove. Backups."},
        {"CANNOT delete backups", "CANNOT delete. Backups."},
        {"without changing files", "Without changing. Files."},
        {"no changes allowed", "No changes. Allowed."},
    };
    for (size_t i = 0; i < sizeof(unsafe_boundaries)/sizeof(unsafe_boundaries[0]); ++i) {
        CHECK(mika_punctuation_preserves_words(unsafe_boundaries[i][0], unsafe_boundaries[i][1]));
        CHECK(!mika_punctuation_output_safe(unsafe_boundaries[i][0], unsafe_boundaries[i][1]));
    }
    CHECK(mika_punctuation_output_safe("do not execute", "Do not execute."));
    CHECK(mika_punctuation_output_safe("don't. inspect files", "Don't. Inspect files."));
    CHECK(mika_punctuation_output_safe("not now inspect files", "Not now, inspect files."));
    CHECK(mika_punctuation_output_safe("notebook changes now inspect files", "Notebook changes. Now inspect files."));
    /* Deliberately beyond the one-word scope: do not claim a semantic parser. */
    CHECK(mika_punctuation_output_safe("not ever execute cleanup", "Not ever execute. Cleanup."));
    CHECK(!mika_punctuation_output_safe(NULL, "text"));
    CHECK(!mika_punctuation_output_safe("text", NULL));
    CHECK(!mika_punctuation_input_valid(NULL));
    CHECK(!mika_punctuation_input_valid("caf\xc3\xa9"));
    CHECK(!mika_punctuation_input_valid("bad\x01"));
    CHECK(!mika_punctuation_preserves_words("test", NULL));
    char word[MIKA_PUNCTUATION_MAX_WORD + 2];
    memset(word, 'x', sizeof(word));
    word[MIKA_PUNCTUATION_MAX_WORD] = 0;
    CHECK(mika_punctuation_input_valid(word));
    word[MIKA_PUNCTUATION_MAX_WORD] = 'x';
    word[MIKA_PUNCTUATION_MAX_WORD + 1] = 0;
    CHECK(!mika_punctuation_input_valid(word));
    char *large = malloc(MIKA_PUNCTUATION_MAX_INPUT + 2u);
    CHECK(large);
    for (size_t i = 0; i < MIKA_PUNCTUATION_MAX_INPUT + 1u; ++i) { large[i] = i % 2 ? ' ' : 'a'; }
    large[MIKA_PUNCTUATION_MAX_INPUT] = 0;
    CHECK(mika_punctuation_input_valid(large));
    CHECK(mika_punctuation_preserves_words(large, large));
    large[MIKA_PUNCTUATION_MAX_INPUT] = 'a';
    large[MIKA_PUNCTUATION_MAX_INPUT + 1u] = 0;
    CHECK(!mika_punctuation_input_valid(large));
    free(large);
    /* Exhaustive byte-level mutations must never introduce a non-case change
     * inside an existing word, including arbitrary controls/high bytes. */
    char mutation[] = "hello world";
    for (size_t i = 0; i < strlen("hello world"); ++i) {
        if (i == 5) { continue; }
        for (unsigned ch = 1; ch < 256; ++ch) {
            strcpy(mutation, "hello world");
            mutation[i] = (char)ch;
            unsigned original = (unsigned char)"hello world"[i];
            int same = ch == original || ch == original - ('a' - 'A');
            CHECK(mika_punctuation_preserves_words("hello world", mutation) == same);
        }
    }
    puts("Punctuation guard checks passed.");
    return 0;
}

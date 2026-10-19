#ifndef MIKA_PUNCTUATION_H
#define MIKA_PUNCTUATION_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MIKA_PUNCTUATION_MAX_INPUT 32768u
#define MIKA_PUNCTUATION_MAX_WORD 96u

/* Conservative ASCII-only envelope for lossless source-offset alignment.
 * Unsupported input stays raw. Empty input is valid; no inference is needed. */
int mika_punctuation_input_valid(const char *raw);
/* Obvious literals, existing camelCase and acronyms retain their source case. */
int mika_punctuation_word_literal(const char *word, size_t length);
/* Only ASCII case changes outside protected literals, whitespace normalization,
 * and at most one appended comma/period/question mark per existing word.
 * Original punctuation is retained. */
int mika_punctuation_preserves_words(const char *raw, const char *candidate);
/* Word preservation plus rejection of a new INTERNAL period/question mark
 * immediately after an English negation or its next word. This is a bounded
 * fallback guard, NOT a semantic guarantee. Original boundaries and final
 * punctuation are retained; the caller uses raw unchanged on rejection. */
int mika_punctuation_output_safe(const char *raw, const char *candidate);

typedef enum {
    MIKA_PUNCTUATION_NONE,
    MIKA_PUNCTUATION_INPUT,
    MIKA_PUNCTUATION_ASSETS,
    MIKA_PUNCTUATION_RUNTIME,
    MIKA_PUNCTUATION_MODEL,
    MIKA_PUNCTUATION_OUTPUT,
    MIKA_PUNCTUATION_MEMORY
} MikaPunctuationFailure;
const char *mika_punctuation_failure_message(MikaPunctuationFailure failure);

typedef int (*MikaPunctuationCancelled)(void *userdata);
/* 0: caller owns *out (free). 1: use raw unchanged. 130: cancel, print nothing.
 * A NULL directory selects the 'punctuation' sibling of the running executable.
 * Does not download, save input, or print transcripts/diagnostics.
 * Optional failure reason contains no input text, paths or native exception data. */
int mika_punctuation_run(const char *directory, const char *raw,
                         MikaPunctuationCancelled cancelled, void *userdata,
                         char **out, MikaPunctuationFailure *failure);

#ifdef __cplusplus
}
#endif
#endif

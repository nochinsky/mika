#ifndef MIKA_PUNCTUATION_H
#define MIKA_PUNCTUATION_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MIKA_PUNCTUATION_MAX_INPUT 32768u
#define MIKA_PUNCTUATION_MAX_WORD 96u

/* Conservative ASCII-only envelope for this experimental English backend.
 * Reject unsupported input rather than passing it to upstream's byte-wise casing.
 * Empty input is valid; no inference is needed. */
int mika_punctuation_input_valid(const char *raw);
/* Obvious code/path/email/numeric tokens keep their original case as well. */
int mika_punctuation_word_literal(const char *word, size_t length);
/* Only ASCII case changes outside protected literals, whitespace normalization,
 * and at most one appended comma/period/question mark per existing word.
 * Original punctuation is retained. */
int mika_punctuation_preserves_words(const char *raw, const char *candidate);

typedef int (*MikaPunctuationCancelled)(void *userdata);
/* 0: caller owns *out (free). 1: use raw unchanged. 130: cancel, print nothing.
 * A NULL directory selects the 'punctuation' sibling of the running executable.
 * Does not download, save input, or print transcripts/diagnostics. */
int mika_punctuation_run(const char *directory, const char *raw,
                         MikaPunctuationCancelled cancelled, void *userdata,
                         char **out);

#ifdef __cplusplus
}
#endif
#endif

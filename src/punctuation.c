#include "punctuation.h"
#include <string.h>

const char *mika_punctuation_failure_message(MikaPunctuationFailure failure)
{
    switch (failure) {
    case MIKA_PUNCTUATION_INPUT: return "text is outside formatting limits";
    case MIKA_PUNCTUATION_ASSETS: return "formatting data is missing, unreadable or corrupted";
    case MIKA_PUNCTUATION_RUNTIME: return "formatting runtime is unavailable";
    case MIKA_PUNCTUATION_MODEL: return "formatting inference failed";
    case MIKA_PUNCTUATION_OUTPUT: return "formatting result was rejected";
    case MIKA_PUNCTUATION_MEMORY: return "not enough memory for formatting";
    default: return "formatting is unavailable";
    }
}

static int space(unsigned char ch)
{
    return ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n' || ch == '\v' || ch == '\f';
}

static unsigned char fold(unsigned char ch)
{
    return ch >= 'A' && ch <= 'Z' ? (unsigned char)(ch + ('a' - 'A')) : ch;
}

int mika_punctuation_input_valid(const char *raw)
{
    if (!raw) { return 0; }
    size_t word = 0;
    for (size_t i = 0; i <= MIKA_PUNCTUATION_MAX_INPUT; ++i) {
        unsigned char ch = (unsigned char)raw[i];
        if (!ch) { return 1; }
        if (ch >= 127 || (ch < 32 && !space(ch))) { return 0; }
        if (space(ch)) { word = 0; }
        else if (++word > MIKA_PUNCTUATION_MAX_WORD) { return 0; }
    }
    return 0;
}

int mika_punctuation_word_literal(const char *word, size_t length)
{
    if (!word || !length || length > MIKA_PUNCTUATION_MAX_WORD) { return 0; }
    if (word[0] == '-') { return 1; }
    /* Ignore ordinary sentence-ending punctuation when looking for internal
     * code structure. Do not attempt brand-name correction or guess spelling. */
    while (length && (word[length - 1] == '.' || word[length - 1] == ',' ||
           word[length - 1] == '?' || word[length - 1] == '!' || word[length - 1] == ':' ||
           word[length - 1] == ';' || word[length - 1] == '"' || word[length - 1] == '\'')) { --length; }
    size_t capitals = 0, letters = 0;
    for (size_t i = 0; i < length; ++i) {
        char ch = word[i];
        if ((ch >= '0' && ch <= '9') || strchr("/\\_@+#=.:<>[]{}$%&|^~`", ch)) { return 1; }
        if (ch >= 'A' && ch <= 'Z') { ++capitals; ++letters; }
        if (ch >= 'a' && ch <= 'z') {
            ++letters;
            /* Existing camelCase/PascalCase is information, not a brand guess. */
            if (i + 1 < length && word[i + 1] >= 'A' && word[i + 1] <= 'Z') { return 1; }
        }
    }
    return letters >= 2 && capitals == letters;
}

/* Recognize a narrow English negation context, not verbs, command spellings or
 * intended meaning. A rejected candidate falls back wholesale to original raw.
 * Original sentence punctuation is never reinterpreted. */
static int negation(const unsigned char *word, const unsigned char *end)
{
    while (end > word && strchr(".,?!:;\"'", end[-1])) { --end; }
    size_t length = (size_t)(end - word);
    static const char *const terms[] = {"not", "no", "never", "without", "cannot"};
    for (size_t i = 0; i < sizeof(terms) / sizeof(terms[0]); ++i) {
        if (strlen(terms[i]) != length) { continue; }
        size_t j = 0;
        while (j < length && fold(word[j]) == (unsigned char)terms[i][j]) { ++j; }
        if (j == length) { return 1; }
    }
    return length >= 4 && fold(end[-3]) == 'n' && end[-2] == '\'' && fold(end[-1]) == 't';
}

static int preserves(const char *raw, const char *candidate, int protect_negation)
{
    if (!mika_punctuation_input_valid(raw) || !candidate) { return 0; }
    /* Bound the result before comparing; the model can add one mark per word. */
    size_t length = 0;
    while (length <= 2u * MIKA_PUNCTUATION_MAX_INPUT + 16u && candidate[length]) {
        unsigned char ch = (unsigned char)candidate[length++];
        if (ch >= 127 || (ch < 32 && !space(ch))) { return 0; }
    }
    if (length > 2u * MIKA_PUNCTUATION_MAX_INPUT + 16u) { return 0; }
    const unsigned char *a = (const unsigned char *)raw;
    const unsigned char *b = (const unsigned char *)candidate;
    int previous_negation = 0;
    for (;;) {
        while (space(*a)) { ++a; }
        while (space(*b)) { ++b; }
        if (!*a || !*b) { return !*a && !*b; }
        const unsigned char *end = a;
        while (*end && !space(*end)) { ++end; }
        int current_negation = protect_negation && negation(a, end);
        int literal = mika_punctuation_word_literal((const char *)a, (size_t)(end - a));
        unsigned char last = 0;
        while (*a && !space(*a)) {
            if (!*b || space(*b) || (literal ? *a != *b : fold(*a) != fold(*b))) { return 0; }
            last = *a++;
            ++b;
        }
        if (*b && !space(*b)) {
            /* Never stack a new mark onto existing punctuation. */
            if (last == '.' || last == ',' || last == '?' || last == '!' ||
                last == ':' || last == ';' || last == '"' || last == '\'') { return 0; }
            if (*b != '.' && *b != ',' && *b != '?') { return 0; }
            const unsigned char *rest = end;
            while (space(*rest)) { ++rest; }
            if (protect_negation && *rest && (*b == '.' || *b == '?') &&
                (current_negation || previous_negation)) { return 0; }
            ++b;
            if (*b && !space(*b)) { return 0; }
        }
        previous_negation = current_negation && last != '.' && last != '?' && last != '!';
    }
}

int mika_punctuation_preserves_words(const char *raw, const char *candidate)
{
    return preserves(raw, candidate, 0);
}

int mika_punctuation_output_safe(const char *raw, const char *candidate)
{
    return preserves(raw, candidate, 1);
}

#include "punctuation.h"

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

int mika_punctuation_preserves_words(const char *raw, const char *candidate)
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
    for (;;) {
        while (space(*a)) { ++a; }
        while (space(*b)) { ++b; }
        if (!*a || !*b) { return !*a && !*b; }
        unsigned char last = 0;
        while (*a && !space(*a)) {
            if (!*b || space(*b) || fold(*a) != fold(*b)) { return 0; }
            last = *a++;
            ++b;
        }
        if (*b && !space(*b)) {
            /* Never stack a new mark onto existing punctuation. */
            if (last == '.' || last == ',' || last == '?' || last == '!' ||
                last == ':' || last == ';' || last == '"' || last == '\'') { return 0; }
            if (*b != '.' && *b != ',' && *b != '?') { return 0; }
            ++b;
            if (*b && !space(*b)) { return 0; }
        }
    }
}

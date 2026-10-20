/* Test-only ABI-compatible library. Never packaged. */
#include "fullstop.h"
#include <chrono>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <thread>

extern "C" MikaFullstop *MikaFullstopOpen(const char *, const char *)
{
    if (std::getenv("MIKA_PUNCT_TEST_CREATE_THROW")) { throw std::runtime_error("test create"); }
    static int token;
    return std::getenv("MIKA_PUNCT_TEST_CREATE_NULL") ? nullptr : reinterpret_cast<MikaFullstop *>(&token);
}
extern "C" void MikaFullstopClose(MikaFullstop *) {}
extern "C" int MikaFullstopApply(MikaFullstop *, const char *raw,
    MikaPunctuationCancelled, void *, char **out)
{
    if (!out) { return 1; }
    *out = nullptr;
    if (std::getenv("MIKA_PUNCT_TEST_SLOW")) {
        std::fputs("punctuation-test: inference started\n", stderr);
        std::fflush(stderr);
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    if (std::getenv("MIKA_PUNCT_TEST_APPLY_THROW")) { throw std::runtime_error(raw); }
    if (std::getenv("MIKA_PUNCT_TEST_APPLY_NULL")) { return 1; }
    const char *value = std::getenv("MIKA_PUNCT_TEST_OUTPUT");
    if (!value) { value = raw; }
    bool huge = std::getenv("MIKA_PUNCT_TEST_HUGE") != nullptr;
    size_t n = huge ? 70000 : std::strlen(value);
    *out = static_cast<char *>(std::malloc(n + 1));
    if (!*out) { return 1; }
    if (huge) { std::memset(*out, 'X', n); (*out)[n] = 0; }
    else { std::memcpy(*out, value, n + 1); }
    return std::getenv("MIKA_PUNCT_TEST_CANCEL") ? 130 : 0;
}
extern "C" void MikaFullstopFreeText(char *text) { std::free(text); }

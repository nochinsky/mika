/* Test-only ABI-compatible library. Never packaged. */
#include <chrono>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <thread>
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif
extern "C" {
EXPORT const void *SherpaOnnxCreateOnlinePunctuation(const void *)
{
    if (std::getenv("MIKA_PUNCT_TEST_CREATE_THROW")) { throw std::runtime_error("test create"); }
    static int token;
    return std::getenv("MIKA_PUNCT_TEST_CREATE_NULL") ? nullptr : &token;
}
EXPORT void SherpaOnnxDestroyOnlinePunctuation(const void *) {}
EXPORT const char *SherpaOnnxOnlinePunctuationAddPunct(const void *, const char *raw)
{
    if (std::getenv("MIKA_PUNCT_TEST_SLOW")) {
        std::fputs("punctuation-test: inference started\n", stderr);
        std::fflush(stderr);
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    if (std::getenv("MIKA_PUNCT_TEST_APPLY_THROW")) { throw std::runtime_error("test apply"); }
    if (std::getenv("MIKA_PUNCT_TEST_APPLY_NULL")) { return nullptr; }
    const char *value = std::getenv("MIKA_PUNCT_TEST_OUTPUT");
    if (!value) { value = raw; }
    bool huge = std::getenv("MIKA_PUNCT_TEST_HUGE") != nullptr;
    size_t n = huge ? 70000 : std::strlen(value);
    char *text = static_cast<char *>(std::malloc(n + 1));
    if (text) {
        if (huge) { std::memset(text, 'X', n); text[n] = 0; }
        else { std::memcpy(text, value, n + 1); }
    }
    return text;
}
EXPORT void SherpaOnnxOnlinePunctuationFreeText(const char *text) { std::free(const_cast<char *>(text)); }
}

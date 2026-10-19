#include "punctuation.h"
#include "assets.h"
extern "C" {
#include "verify.h"
#include "platform.h"
}
#include "fullstop.h"

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <string>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace {
namespace fs = std::filesystem;

class Library {
 public:
    explicit Library(const fs::path &path) {
#ifdef _WIN32
        handle_ = LoadLibraryExW(path.c_str(), nullptr,
            LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
        if (handle_) {
            HMODULE pinned = nullptr;
            if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                                   reinterpret_cast<LPCWSTR>(handle_), &pinned)) {
                FreeLibrary(handle_);
                handle_ = nullptr;
            }
        }
#elif defined(__APPLE__)
        handle_ = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
#else
        handle_ = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL | RTLD_NODELETE);
#endif
        if (!handle_) { throw std::runtime_error("punctuation library"); }
    }
    ~Library() {
        /* Keep runtime/tokenizer code and registries mapped until process exit.
         * Sessions and returned text are freed promptly; no resident service. */
#ifdef _WIN32
        FreeLibrary(handle_);
#elif !defined(__APPLE__)
        dlclose(handle_);
#endif
        /* Darwin has no portable RTLD_NODELETE. Intentionally retain the dlopen
         * reference until process exit, just as we pin modules on Windows. */
    }
    Library(const Library &) = delete;
    Library &operator=(const Library &) = delete;
    template<class Function> Function symbol(const char *name) const {
#ifdef _WIN32
        auto address = GetProcAddress(handle_, name);
#else
        auto address = dlsym(handle_, name);
#endif
        if (!address) { throw std::runtime_error("punctuation entry point"); }
        static_assert(sizeof(Function) == sizeof(address), "Native function pointer size");
        Function function;
        std::memcpy(&function, &address, sizeof(function));
        return function;
    }
 private:
#ifdef _WIN32
    HMODULE handle_ = nullptr;
#else
    void *handle_ = nullptr;
#endif
};

bool stop(MikaPunctuationCancelled cancelled, void *userdata)
{
    return mika_cancelled(nullptr) || (cancelled && cancelled(userdata));
}
}

extern "C" int mika_punctuation_run(const char *directory, const char *raw,
    MikaPunctuationCancelled cancelled, void *userdata, char **out, MikaPunctuationFailure *failure)
{
    if (failure) { *failure = MIKA_PUNCTUATION_NONE; }
    const auto fail = [failure](MikaPunctuationFailure reason) {
        if (failure) { *failure = reason; }
        return 1;
    };
    if (!out) { return fail(MIKA_PUNCTUATION_OUTPUT); }
    *out = nullptr;
    MikaPunctuationFailure stage = MIKA_PUNCTUATION_MEMORY;
    try {
        if (stop(cancelled, userdata)) { return 130; }
        if (!mika_punctuation_input_valid(raw)) { return fail(MIKA_PUNCTUATION_INPUT); }
        size_t raw_length = std::strlen(raw);
        if (std::strspn(raw, " \t\r\n\v\f") == raw_length) {
            *out = static_cast<char *>(std::malloc(raw_length + 1));
            if (*out) { std::memcpy(*out, raw, raw_length + 1); }
            return *out ? 0 : fail(MIKA_PUNCTUATION_MEMORY);
        }
        stage = MIKA_PUNCTUATION_ASSETS;
        std::unique_ptr<char, decltype(&std::free)> location(
            directory ? nullptr : mika_asset_path("punctuation"), &std::free);
        if (!directory && !location) { return fail(stage); }
        fs::path base = directory ? fs::absolute(fs::u8path(directory)) : fs::u8path(location.get());
        std::string model = (base / "model.int8.onnx").u8string();
        std::string vocab = (base / "sp.model").u8string();
        stage = MIKA_PUNCTUATION_ASSETS;
        int a = mika_model_verify(model.c_str(), 52883510,
            "d69b2df2db21c177b8ea9086e2324796176fb5a28fa8893f9df11b79bf3fc3ec");
        int b = mika_model_verify(vocab.c_str(), 587902,
            "9e86d0263de80b3b68327a21f5350c8cdf846e4c4400253c9baf05e3d44871c3");
        if (a == 130 || b == 130 || stop(cancelled, userdata)) { return 130; }
        if (a != MIKA_MODEL_VALID || b != MIKA_MODEL_VALID) { return fail(stage); }
        stage = MIKA_PUNCTUATION_RUNTIME;
#ifdef _WIN32
        Library runtime(base / "onnxruntime.dll");
        Library backend(base / "mika-fullstop.dll");
#elif defined(__APPLE__)
        Library runtime(base / "libonnxruntime.dylib");
        Library backend(base / "libmika-fullstop.dylib");
#else
        Library runtime(base / "libonnxruntime.so");
        Library backend(base / "libmika-fullstop.so");
#endif
        auto create = backend.symbol<decltype(&MikaFullstopOpen)>("MikaFullstopOpen");
        auto destroy = backend.symbol<decltype(&MikaFullstopClose)>("MikaFullstopClose");
        auto apply = backend.symbol<decltype(&MikaFullstopApply)>("MikaFullstopApply");
        auto free_text = backend.symbol<decltype(&MikaFullstopFreeText)>("MikaFullstopFreeText");
        stage = MIKA_PUNCTUATION_MODEL;
        std::unique_ptr<MikaFullstop, decltype(destroy)> punct(create(model.c_str(), vocab.c_str()), destroy);
        if (stop(cancelled, userdata)) { return 130; }
        if (!punct) { return fail(stage); }
        struct Cancellation { MikaPunctuationCancelled callback; void *data; } state{cancelled, userdata};
        auto poll = [](void *data) -> int {
            auto *s = static_cast<Cancellation *>(data);
            return stop(s->callback, s->data) ? 1 : 0;
        };
        char *candidate = nullptr;
        int code;
        try { code = apply(punct.get(), raw, poll, &state, &candidate); }
        catch (...) { if (candidate) { free_text(candidate); } throw; }
        std::unique_ptr<char, decltype(free_text)> text(candidate, free_text);
        if (code == 130 || stop(cancelled, userdata)) { return 130; }
        if (code || !text) { return fail(stage); }
        stage = MIKA_PUNCTUATION_OUTPUT;
        if (!mika_punctuation_preserves_words(raw, text.get())) { return fail(stage); }
        size_t length = std::strlen(text.get());
        stage = MIKA_PUNCTUATION_MEMORY;
        *out = static_cast<char *>(std::malloc(length + 1));
        if (!*out) { return fail(stage); }
        std::memcpy(*out, text.get(), length + 1);
        return 0;
    } catch (...) {
        /* Do not let a formatting model's C++ exception lose dictation.
         * Native crashes/abort/OOM-killer are not recoverable in-process. */
        return stop(cancelled, userdata) ? 130 : fail(stage);
    }
}

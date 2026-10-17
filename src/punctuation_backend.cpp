#include "punctuation.h"
extern "C" {
#include "model.h"
#include "platform.h"
}
#include "fullstop.h"

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <dlfcn.h>
#include <unistd.h>
#endif

namespace {
namespace fs = std::filesystem;

fs::path executable_directory()
{
#ifdef _WIN32
    std::vector<wchar_t> path(32768);
    DWORD n = GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
    if (!n || n >= path.size()) { throw std::runtime_error("executable path"); }
    return fs::path(std::wstring(path.data(), n)).parent_path();
#else
    std::vector<char> path(32768);
    ssize_t n = readlink("/proc/self/exe", path.data(), path.size());
    if (n < 0 || static_cast<size_t>(n) >= path.size()) { throw std::runtime_error("executable path"); }
    return fs::path(std::string(path.data(), static_cast<size_t>(n))).parent_path();
#endif
}

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
#else
        dlclose(handle_);
#endif
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
    MikaPunctuationCancelled cancelled, void *userdata, char **out)
{
    if (!out) { return 1; }
    *out = nullptr;
    try {
        if (stop(cancelled, userdata)) { return 130; }
        if (!mika_punctuation_input_valid(raw)) { return 1; }
        size_t raw_length = std::strlen(raw);
        if (std::strspn(raw, " \t\r\n\v\f") == raw_length) {
            *out = static_cast<char *>(std::malloc(raw_length + 1));
            if (*out) { std::memcpy(*out, raw, raw_length + 1); }
            return *out ? 0 : 1;
        }
        fs::path base = directory ? fs::absolute(fs::u8path(directory))
                                  : executable_directory() / "punctuation";
        std::string model = (base / "model.int8.onnx").u8string();
        std::string vocab = (base / "sp.model").u8string();
        int a = mika_model_verify(model.c_str(), 52883510,
            "d69b2df2db21c177b8ea9086e2324796176fb5a28fa8893f9df11b79bf3fc3ec");
        int b = mika_model_verify(vocab.c_str(), 587902,
            "9e86d0263de80b3b68327a21f5350c8cdf846e4c4400253c9baf05e3d44871c3");
        if (a == 130 || b == 130 || stop(cancelled, userdata)) { return 130; }
        if (a != MIKA_MODEL_VALID || b != MIKA_MODEL_VALID) { return 1; }
#ifdef _WIN32
        Library runtime(base / "onnxruntime.dll");
        Library backend(base / "mika-fullstop.dll");
#else
        Library runtime(base / "libonnxruntime.so");
        Library backend(base / "libmika-fullstop.so");
#endif
        auto create = backend.symbol<decltype(&MikaFullstopOpen)>("MikaFullstopOpen");
        auto destroy = backend.symbol<decltype(&MikaFullstopClose)>("MikaFullstopClose");
        auto apply = backend.symbol<decltype(&MikaFullstopApply)>("MikaFullstopApply");
        auto free_text = backend.symbol<decltype(&MikaFullstopFreeText)>("MikaFullstopFreeText");
        std::unique_ptr<MikaFullstop, decltype(destroy)> punct(create(model.c_str(), vocab.c_str()), destroy);
        if (stop(cancelled, userdata)) { return 130; }
        if (!punct) { return 1; }
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
        if (code || !text || !mika_punctuation_preserves_words(raw, text.get())) { return 1; }
        size_t length = std::strlen(text.get());
        *out = static_cast<char *>(std::malloc(length + 1));
        if (!*out) { return 1; }
        std::memcpy(*out, text.get(), length + 1);
        return 0;
    } catch (...) {
        /* Do not let an optional native model's C++ exception lose dictation.
         * Native crashes/abort/OOM-killer are not recoverable in-process. */
        return stop(cancelled, userdata) ? 130 : 1;
    }
}

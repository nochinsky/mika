#include "punctuation.h"
extern "C" {
#include "model.h"
#include "platform.h"
}
#include "c-api.h"

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
        /* Keep SDK code/global registries mapped until process exit. Unloading
         * this prebuilt SDK leaks static registry allocations and risks dangling
         * TLS destructors. Sessions and returned text are still freed promptly.
         * Mika performs one formatting stage then exits; no resident service. */
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
        std::string vocab = (base / "bpe.vocab").u8string();
        int a = mika_model_verify(model.c_str(), 7490500,
            "9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e");
        int b = mika_model_verify(vocab.c_str(), 149430,
            "e118b7ad88c54db562517df49e1cffd4836d166c34fb190fd311d7f34eb238f5");
        if (a == 130 || b == 130 || stop(cancelled, userdata)) { return 130; }
        if (a != MIKA_MODEL_VALID || b != MIKA_MODEL_VALID) { return 1; }
#ifdef _WIN32
        Library runtime(base / "onnxruntime.dll");
        Library backend(base / "sherpa-onnx-c-api.dll");
#else
        Library runtime(base / "libonnxruntime.so");
        Library backend(base / "libsherpa-onnx-c-api.so");
#endif
        auto create = backend.symbol<decltype(&SherpaOnnxCreateOnlinePunctuation)>(
            "SherpaOnnxCreateOnlinePunctuation");
        auto destroy = backend.symbol<decltype(&SherpaOnnxDestroyOnlinePunctuation)>(
            "SherpaOnnxDestroyOnlinePunctuation");
        auto apply = backend.symbol<decltype(&SherpaOnnxOnlinePunctuationAddPunct)>(
            "SherpaOnnxOnlinePunctuationAddPunct");
        auto free_text = backend.symbol<decltype(&SherpaOnnxOnlinePunctuationFreeText)>(
            "SherpaOnnxOnlinePunctuationFreeText");
        SherpaOnnxOnlinePunctuationConfig config{};
        config.model.cnn_bilstm = model.c_str();
        config.model.bpe_vocab = vocab.c_str();
        config.model.num_threads = 1;
        config.model.provider = "cpu";
        std::unique_ptr<const SherpaOnnxOnlinePunctuation, decltype(destroy)> punct(create(&config), destroy);
        if (stop(cancelled, userdata)) { return 130; }
        if (!punct) { return 1; }
        std::unique_ptr<const char, decltype(free_text)> text(apply(punct.get(), raw), free_text);
        if (stop(cancelled, userdata)) { return 130; }
        if (!text || !mika_punctuation_preserves_words(raw, text.get())) { return 1; }
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

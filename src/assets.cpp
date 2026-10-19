#include "assets.h"
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#else
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif
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
#elif defined(__APPLE__)
    uint32_t length = 0;
    _NSGetExecutablePath(nullptr, &length);
    if (!length || length > 1048576u) { throw std::runtime_error("executable path"); }
    std::vector<char> path(length);
    if (_NSGetExecutablePath(path.data(), &length) != 0) { throw std::runtime_error("executable path"); }
    return fs::canonical(fs::path(path.data())).parent_path();
#else
    std::vector<char> path(32768);
    ssize_t n = readlink("/proc/self/exe", path.data(), path.size());
    if (n < 0 || static_cast<size_t>(n) >= path.size()) { throw std::runtime_error("executable path"); }
    return fs::path(std::string(path.data(), static_cast<size_t>(n))).parent_path();
#endif
}
}

extern "C" char *mika_asset_path(const char *relative)
{
    try {
        if (!relative || !*relative) { return nullptr; }
        fs::path suffix = fs::u8path(relative);
        if (suffix.has_root_path()) { return nullptr; }
        for (const auto &component : suffix) {
            if (component == "..") { return nullptr; }
        }
        std::string path = (executable_directory() / suffix).u8string();
        char *copy = static_cast<char *>(std::malloc(path.size() + 1));
        if (copy) { std::memcpy(copy, path.c_str(), path.size() + 1); }
        return copy;
    } catch (...) {
        return nullptr;
    }
}

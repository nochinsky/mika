#include "assets.h"
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>

int main(int argc, char **argv)
{
    namespace fs = std::filesystem;
    if (argc != 1) { return 1; }
    char *path = mika_asset_path("speech/silero-vad-v6.2-F32.gguf");
    fs::path expected = fs::canonical(fs::u8path(argv[0])).parent_path() / "speech/silero-vad-v6.2-F32.gguf";
    bool good = path && fs::u8path(path) == expected;
    std::free(path);
    for (const char *invalid : {"", "../outside", "speech/../../outside", "/absolute"}) {
        path = mika_asset_path(invalid);
        good = good && !path;
        std::free(path);
    }
    good = good && !mika_asset_path(nullptr);
    path = mika_asset_path("speech/Unicode \xc3\xbc.txt");
    good = good && path && fs::u8path(path).filename().u8string() == "Unicode \xc3\xbc.txt";
    std::free(path);
    std::puts(good ? "PASS: executable-relative UTF-8 asset paths and invalid path rejection" : "FAIL: bundled asset path resolution");
    return good ? 0 : 1;
}

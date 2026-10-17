#include "fullstop_render.hpp"
#include "punctuation.h"
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <string>
#include <vector>

#define CHECK(condition) do { if (!(condition)) { std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); std::exit(1); } } while (0)

template<class Function> void rejected(Function function) {
    bool caught = false;
    try { function(); } catch (const std::exception &) { caught = true; }
    CHECK(caught);
}

int main()
{
    CHECK(mika_fullstop_canonicalize(" \t hello\r\nworld \v\f") == "hello world");
    CHECK(mika_fullstop_canonicalize("").empty());
    CHECK(mika_fullstop_canonicalize(" \n ").empty());
    rejected([] { mika_fullstop_canonicalize(nullptr); });
    rejected([] { mika_fullstop_canonicalize("caf\xc3\xa9"); });
    rejected([] { mika_fullstop_canonicalize(std::string(97, 'a').c_str()); });

    std::vector<MikaFullstopPiece> pieces = {{0, 5, u8"▁hello", false}, {5, 11, u8"▁world", false}};
    std::vector<MikaFullstopPrediction> predictions(2);
    predictions[0].capitals[1] = 1; predictions[0].post = 3;
    predictions[1].post = 2;
    CHECK(mika_fullstop_render("hello world", pieces, predictions) == "Hello, world.");

    pieces = {{0, 4, u8"▁five", false}, {4, 5, "<unk>", true},
              {5, 11, "minute", false}, {11, 16, u8"▁test", false}};
    predictions.assign(4, {});
    predictions[0].capitals[1] = 1;
    predictions[0].post = 2; // No punctuation inside the original five-minute token.
    predictions[1].capitals.fill(1);
    predictions[1].post = 4;
    predictions[3].post = 2;
    CHECK(mika_fullstop_render("five-minute test", pieces, predictions) == "Five-minute test.");

    pieces = {{0, 3, u8"▁usa", false}};
    predictions.assign(1, {});
    predictions[0].capitals.fill(1); predictions[0].pre = 1; predictions[0].post = 1;
    CHECK(mika_fullstop_render("usa", pieces, predictions) == "USA"); // No U.S.A. rewrite.

    pieces = {{0, 6, u8"▁hello.", false}};
    predictions[0].post = 2; predictions[0].pre = 0; predictions[0].capitals.fill(0);
    predictions[0].capitals[1] = 1;
    CHECK(mika_fullstop_render("hello.", pieces, predictions) == "Hello.");

    pieces = {{0, 4, "<unk>", true}};
    predictions[0].capitals.fill(1); predictions[0].post = 0;
    CHECK(mika_fullstop_render("-@[]", pieces, predictions) == "-@[]");

    pieces = {{0, 12, u8"▁src/file.cpp", false}};
    predictions[0].post = 2;
    CHECK(mika_fullstop_render("src/file.cpp", pieces, predictions) == "src/file.cpp.");
    predictions[0].post = 0;

    pieces = {{0, 5, u8"▁other", false}}; // Unalignable normalization keeps original characters/case.
    CHECK(mika_fullstop_render("MiXeD", pieces, predictions) == "MiXeD");
    pieces = {{0, 20, std::string(20, 'a'), false}};
    CHECK(mika_fullstop_render(std::string(20, 'a'), pieces, predictions) == std::string(20, 'a'));
    pieces = {{0, 0, u8"▁", false}, {0, 5, "hello", false}};
    predictions.assign(2, {}); predictions[1].capitals[0] = 1;
    CHECK(mika_fullstop_render("hello", pieces, predictions) == "Hello");

    rejected([&] { mika_fullstop_render("hello", pieces, {}); });
    pieces = {{4, 3, "bad", false}}; predictions.assign(1, {});
    rejected([&] { mika_fullstop_render("hello", pieces, predictions); });
    pieces = {{0, 6, "bad", false}};
    rejected([&] { mika_fullstop_render("hello", pieces, predictions); });
    pieces = {{0, 5, "hello", false}};
    for (int64_t value : {-1, 5}) {
        predictions[0].post = value;
        rejected([&] { mika_fullstop_render("hello", pieces, predictions); });
    }
    predictions[0].post = 0; predictions[0].pre = 2;
    rejected([&] { mika_fullstop_render("hello", pieces, predictions); });
    predictions[0].pre = 0; predictions[0].capitals[0] = 2;
    rejected([&] { mika_fullstop_render("hello", pieces, predictions); });
    predictions[0].capitals[0] = 0;
    rejected([&] { mika_fullstop_render(std::string("a\0b", 3), pieces, predictions); });
    pieces = {{0, 4, "hell", false}, {3, 5, "lo", false}}; predictions.assign(2, {});
    rejected([&] { mika_fullstop_render("hello", pieces, predictions); });

    // Deterministic mixed-literal stress: arbitrary legal predictions never
    // replace, remove, duplicate or reorder a source character/word.
    for (size_t n = 1; n <= 200; ++n) {
        std::string source;
        pieces.clear(); predictions.clear();
        for (size_t i = 0; i < n; ++i) {
            const size_t begin = source.size();
            if (i) { source += ' '; }
            const std::string word = i % 3 == 0 ? "a-b_12" : i % 3 == 1 ? "can't" : "xyz";
            source += word;
            pieces.push_back({begin, source.size(), std::string(u8"▁") + word, i % 7 == 0});
            MikaFullstopPrediction prediction;
            prediction.pre = static_cast<int64_t>(i % 2);
            prediction.post = static_cast<int64_t>(i % 5);
            for (size_t j = 0; j < prediction.capitals.size(); ++j) {
                prediction.capitals[j] = static_cast<unsigned char>((i + j) % 2);
            }
            predictions.push_back(prediction);
        }
        auto output = mika_fullstop_render(source, pieces, predictions);
        CHECK(mika_punctuation_preserves_words(source.c_str(), output.c_str()));
    }
    std::puts("FullStop source-offset renderer checks passed");
    return 0;
}

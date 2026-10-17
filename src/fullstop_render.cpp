#include "fullstop_render.hpp"
#include "punctuation.h"

#include <stdexcept>
#include <string_view>

namespace {
bool space(char ch) { return ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n' || ch == '\v' || ch == '\f'; }
char lower(char ch) { return ch >= 'A' && ch <= 'Z' ? static_cast<char>(ch + ('a' - 'A')) : ch; }
char upper(char ch) { return ch >= 'a' && ch <= 'z' ? static_cast<char>(ch - ('a' - 'A')) : ch; }
bool existing_boundary(char ch) {
    return ch == '.' || ch == ',' || ch == '?' || ch == '!' || ch == ':' || ch == ';' || ch == '"' || ch == '\'';
}
}

std::string mika_fullstop_canonicalize(const char *raw)
{
    if (!mika_punctuation_input_valid(raw)) { throw std::invalid_argument("unsupported formatting input"); }
    std::string source;
    bool gap = false;
    for (const char *p = raw; *p; ++p) {
        if (space(*p)) { gap = !source.empty(); }
        else {
            if (gap) { source.push_back(' '); gap = false; }
            source.push_back(*p);
        }
    }
    return source;
}

std::string mika_fullstop_render(const std::string &source,
    const std::vector<MikaFullstopPiece> &pieces,
    const std::vector<MikaFullstopPrediction> &predictions)
{
    if (!mika_punctuation_input_valid(source.c_str()) || source.find('\0') != std::string::npos ||
        pieces.size() != predictions.size() || pieces.size() > MIKA_PUNCTUATION_MAX_INPUT + 1u) {
        throw std::invalid_argument("invalid formatting mapping");
    }
    std::string cased = source;
    std::vector<unsigned char> literal(source.size(), 0);
    for (size_t begin = 0; begin < source.size();) {
        if (space(source[begin])) { ++begin; continue; }
        size_t end = begin;
        while (end < source.size() && !space(source[end])) { ++end; }
        if (mika_punctuation_word_literal(source.data() + begin, end - begin)) {
            for (size_t j = begin; j < end; ++j) { literal[j] = 1; }
        }
        begin = end;
    }
    std::vector<char> suffix(source.size() + 1u, 0);
    size_t previous_end = 0;
    for (size_t i = 0; i < pieces.size(); ++i) {
        const auto &piece = pieces[i];
        const auto &prediction = predictions[i];
        if (piece.begin > piece.end || piece.end > source.size() || piece.begin < previous_end ||
            prediction.pre < 0 || prediction.pre > 1 || prediction.post < 0 || prediction.post > 4) {
            throw std::invalid_argument("invalid formatting prediction");
        }
        previous_end = piece.end;
        for (auto bit : prediction.capitals) {
            if (bit > 1) { throw std::invalid_argument("invalid casing prediction"); }
        }
        /* Unknown pieces can represent hyphens, symbols or whole unfamiliar
         * spans. Their source is retained verbatim, never rendered as <unk>. */
        if (!piece.unknown) {
            std::string_view normalized(piece.normalized);
            size_t cap = 0;
            if (normalized.substr(0, 3) == "\xe2\x96\x81") {
                normalized.remove_prefix(3); cap = 1;
            }
            size_t begin = piece.begin;
            while (begin < piece.end && space(source[begin])) { ++begin; }
            bool aligned = normalized.size() == piece.end - begin &&
                           normalized.size() + cap <= prediction.capitals.size();
            for (size_t j = 0; aligned && j < normalized.size(); ++j) {
                unsigned char ch = static_cast<unsigned char>(normalized[j]);
                aligned = ch >= 32 && ch < 127 && lower(source[begin + j]) == lower(normalized[j]);
            }
            /* NFKC/normalizer mismatches are not permission to replace source
             * characters. Leave that span's case unchanged if mapping is unclear. */
            if (aligned) {
                for (size_t j = 0; j < normalized.size(); ++j) {
                    char original = source[begin + j];
                    if (!literal[begin + j]) {
                        cased[begin + j] = prediction.capitals[cap + j] ? upper(original) : lower(original);
                    }
                }
            }
        }
        /* Only complete original words may receive a suffix. Ignore pre-punct
         * and acronym-internal periods: neither is allowed by our word contract.
         * No invented final punctuation, dictionary, spelling or sentence rules. */
        if (piece.end > piece.begin && !space(source[piece.end - 1]) &&
            (piece.end == source.size() || space(source[piece.end])) &&
            !existing_boundary(source[piece.end - 1])) {
            static constexpr char marks[] = {0, 0, '.', ',', '?'};
            suffix[piece.end] = marks[prediction.post];
        }
    }
    std::string result;
    result.reserve(source.size() * 2u + 1u);
    for (size_t i = 0; i < source.size(); ++i) {
        result.push_back(cased[i]);
        if (suffix[i + 1u]) { result.push_back(suffix[i + 1u]); }
    }
    if (!mika_punctuation_preserves_words(source.c_str(), result.c_str())) {
        throw std::runtime_error("unsafe formatting result");
    }
    return result;
}

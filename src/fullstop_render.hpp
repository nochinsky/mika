#ifndef MIKA_FULLSTOP_RENDER_HPP
#define MIKA_FULLSTOP_RENDER_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

/* Private native renderer: source offsets, never model-generated replacement text. */
struct MikaFullstopPiece {
    size_t begin;
    size_t end;
    std::string normalized;
    bool unknown;
};
struct MikaFullstopPrediction {
    int64_t pre = 0;
    int64_t post = 0;
    std::array<unsigned char, 16> capitals{};
};
std::string mika_fullstop_canonicalize(const char *raw);
std::string mika_fullstop_render(const std::string &source,
    const std::vector<MikaFullstopPiece> &pieces,
    const std::vector<MikaFullstopPrediction> &predictions);

#endif

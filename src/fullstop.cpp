#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#endif
#include "fullstop.h"
#include "fullstop_render.hpp"
#include <onnxruntime_cxx_api.h>
#include <sentencepiece_processor.h>

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

struct MikaFullstop {
    Ort::Env environment{ORT_LOGGING_LEVEL_ERROR, "mika"};
    sentencepiece::SentencePieceProcessor tokenizer;
    Ort::Session session{nullptr};
};

namespace {
bool stop(MikaPunctuationCancelled cancelled, void *userdata) {
    return cancelled && cancelled(userdata);
}
void shape(const Ort::Value &value, ONNXTensorElementDataType type,
           const std::vector<int64_t> &expected) {
    if (!value.IsTensor()) { throw std::runtime_error("non-tensor prediction"); }
    auto info = value.GetTensorTypeAndShapeInfo();
    if (info.GetElementType() != type || info.GetShape() != expected) {
        throw std::runtime_error("unexpected prediction shape/type");
    }
}
}

extern "C" MikaFullstop *MikaFullstopOpen(const char *model, const char *vocab)
{
    try {
        if (!model || !vocab) { return nullptr; }
        auto context = std::make_unique<MikaFullstop>();
        context->environment.DisableTelemetryEvents();
        /* Do not give a narrow Windows filename to the tokenizer. Load via
         * filesystem's native UTF-16 path and pass serialized model bytes. */
        std::ifstream file(std::filesystem::u8path(vocab), std::ios::binary);
        if (!file) { return nullptr; }
        std::string serialized(587902, '\0');
        if (!file.read(serialized.data(), static_cast<std::streamsize>(serialized.size())) ||
            file.peek() != std::char_traits<char>::eof() ||
            !context->tokenizer.LoadFromSerializedProto(serialized).ok() ||
            context->tokenizer.GetPieceSize() != 32000) { return nullptr; }
        Ort::SessionOptions options;
        options.SetIntraOpNumThreads(1);
        options.SetInterOpNumThreads(1);
        context->session = Ort::Session(context->environment, std::filesystem::u8path(model).c_str(), options);
        if (context->session.GetInputCount() != 1 || context->session.GetOutputCount() != 4) { return nullptr; }
        return context.release();
    } catch (...) { return nullptr; }
}

extern "C" void MikaFullstopClose(MikaFullstop *model) { delete model; }
extern "C" void MikaFullstopFreeText(char *text) { std::free(text); }

extern "C" int MikaFullstopApply(MikaFullstop *model, const char *raw,
    MikaPunctuationCancelled cancelled, void *userdata, char **out)
{
    if (!out) { return 1; }
    *out = nullptr;
    try {
        if (!model) { return 1; }
        if (stop(cancelled, userdata)) { return 130; }
        const std::string source = mika_fullstop_canonicalize(raw);
        sentencepiece::ImmutableSentencePieceText encoded;
        if (!model->tokenizer.Encode(source, encoded.mutable_proto()).ok() ||
            encoded.text() != source ||
            static_cast<size_t>(encoded.pieces_size()) > MIKA_PUNCTUATION_MAX_INPUT + 1u ||
            (!source.empty() && !encoded.pieces_size())) { return 1; }
        const size_t count = static_cast<size_t>(encoded.pieces_size());
        std::vector<MikaFullstopPiece> pieces;
        std::vector<int64_t> ids;
        pieces.reserve(count); ids.reserve(count);
        for (size_t i = 0; i < count; ++i) {
            const auto piece = encoded.pieces(static_cast<int>(i));
            if (piece.begin() > piece.end() || piece.end() > source.size() ||
                piece.id() >= static_cast<unsigned>(model->tokenizer.GetPieceSize())) { return 1; }
            pieces.push_back({piece.begin(), piece.end(), piece.piece(), model->tokenizer.IsUnknown(static_cast<int>(piece.id()))});
            ids.push_back(static_cast<int64_t>(piece.id()));
        }
        std::vector<MikaFullstopPrediction> predictions(count);
        const auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        const char *inputs[] = {"input_ids"};
        const char *outputs[] = {"pre_preds", "post_preds", "cap_preds", "seg_preds"};
        constexpr size_t body = 254, overlap = 16;
        /* Sequential windows bound attention/arena memory and permit queued
         * cancellation between calls, rather than batching the whole transcript. */
        for (size_t start = 0; start < count; start += body - overlap) {
            if (stop(cancelled, userdata)) { return 130; }
            const size_t end = std::min(start + body, count);
            std::vector<int64_t> window;
            window.reserve(end - start + 2u);
            window.push_back(model->tokenizer.bos_id());
            window.insert(window.end(), ids.begin() + static_cast<ptrdiff_t>(start), ids.begin() + static_cast<ptrdiff_t>(end));
            window.push_back(model->tokenizer.eos_id());
            const int64_t n = static_cast<int64_t>(window.size());
            const int64_t dimensions[] = {1, n};
            auto tensor = Ort::Value::CreateTensor<int64_t>(memory, window.data(), window.size(), dimensions, 2);
            auto values = model->session.Run(Ort::RunOptions{nullptr}, inputs, &tensor, 1, outputs, 4);
            if (stop(cancelled, userdata)) { return 130; }
            if (values.size() != 4) { return 1; }
            shape(values[0], ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64, {1, n});
            shape(values[1], ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64, {1, n});
            shape(values[2], ONNX_TENSOR_ELEMENT_DATA_TYPE_BOOL, {1, n, 16});
            shape(values[3], ONNX_TENSOR_ELEMENT_DATA_TYPE_BOOL, {1, n});
            const auto *pre = values[0].GetTensorData<int64_t>();
            const auto *post = values[1].GetTensorData<int64_t>();
            const auto *caps = static_cast<const unsigned char *>(values[2].GetTensorRawData());
            const auto *segments = static_cast<const unsigned char *>(values[3].GetTensorRawData());
            const size_t keep_begin = start == 0 ? 0 : overlap / 2u;
            const size_t keep_end = end == count ? end - start : end - start - overlap / 2u;
            for (size_t local = keep_begin; local < keep_end; ++local) {
                auto &prediction = predictions[start + local];
                const size_t index = local + 1u; // BOS is not part of the source.
                prediction.pre = pre[index]; prediction.post = post[index];
                if (segments[index] > 1) { return 1; }
                std::copy_n(caps + index * 16u, 16, prediction.capitals.begin());
            }
            if (end == count) { break; }
        }
        if (stop(cancelled, userdata)) { return 130; }
        const auto text = mika_fullstop_render(source, pieces, predictions);
        if (stop(cancelled, userdata)) { return 130; }
        *out = static_cast<char *>(std::malloc(text.size() + 1u));
        if (!*out) { return 1; }
        std::memcpy(*out, text.c_str(), text.size() + 1u);
        return 0;
    } catch (...) {
        /* ORT, tokenizer, renderer and allocation exceptions never cross the ABI. */
        return 1;
    }
}

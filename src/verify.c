#include "verify.h"
#include "platform.h"

#include <openssl/evp.h>
#include <errno.h>
#include <string.h>

void mika_sha256_hex(const unsigned char digest[32], char hex[65])
{
    static const char digits[] = "0123456789abcdef";
    for (size_t i = 0; i < 32; ++i) {
        hex[2 * i] = digits[digest[i] >> 4];
        hex[2 * i + 1] = digits[digest[i] & 15];
    }
    hex[64] = '\0';
}

int mika_model_verify(const char *path, uint64_t expected_bytes, const char *expected_sha256)
{
    if (mika_cancelled(NULL)) { return 130; }
    FILE *file = mika_fopen(path, "rb");
    if (!file) { return errno == ENOENT ? MIKA_MODEL_INVALID : MIKA_MODEL_IO_ERROR; }
    uint64_t file_bytes = 0;
    int result = MIKA_MODEL_INVALID;
    EVP_MD_CTX *hash = NULL;
    if (mika_file_size(file, &file_bytes) != 0) { goto done; }
    if (file_bytes != expected_bytes) { goto done; }
    hash = EVP_MD_CTX_new();
    if (!hash || EVP_DigestInit_ex(hash, EVP_sha256(), NULL) != 1) {
        result = MIKA_MODEL_IO_ERROR;
        goto done;
    }
    unsigned char buffer[65536];
    uint64_t total = 0;
    size_t bytes;
    while ((bytes = fread(buffer, 1, sizeof(buffer), file)) > 0) {
        if (mika_cancelled(NULL)) { result = 130; goto done; }
        if ((uint64_t)bytes > expected_bytes - total) { goto done; }
        total += (uint64_t)bytes;
        if (EVP_DigestUpdate(hash, buffer, bytes) != 1) { result = MIKA_MODEL_IO_ERROR; goto done; }
    }
    if (ferror(file)) { result = MIKA_MODEL_IO_ERROR; goto done; }
    if (total == expected_bytes) {
        unsigned char digest[EVP_MAX_MD_SIZE];
        unsigned digest_bytes = 0;
        char hex[65];
        if (EVP_DigestFinal_ex(hash, digest, &digest_bytes) != 1 || digest_bytes != 32) {
            result = MIKA_MODEL_IO_ERROR;
            goto done;
        }
        mika_sha256_hex(digest, hex);
        result = strcmp(hex, expected_sha256) == 0 ? MIKA_MODEL_VALID : MIKA_MODEL_INVALID;
    }
done:
    EVP_MD_CTX_free(hash);
    if (fclose(file) != 0 && result == MIKA_MODEL_VALID) { result = MIKA_MODEL_IO_ERROR; }
    return result;
}

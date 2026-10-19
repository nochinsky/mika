#ifndef MIKA_VERIFY_H
#define MIKA_VERIFY_H

#include <stdint.h>

enum { MIKA_MODEL_VALID = 0, MIKA_MODEL_INVALID = 1, MIKA_MODEL_IO_ERROR = 2 };

/* Fixed size and full SHA-256, read-only regular files; 130 on interruption. */
int mika_model_verify(const char *path, uint64_t expected_bytes, const char *expected_sha256);
void mika_sha256_hex(const unsigned char digest[32], char hex[65]);

#endif

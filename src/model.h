#ifndef MIKA_MODEL_H
#define MIKA_MODEL_H

#include "platform.h"
#include "verify.h"
#include <stdint.h>

#define MIKA_MODEL_FILE "granite-speech-5.0-470m-turboctc-Q4_K_M.gguf"
#define MIKA_MODEL_REVISION "0cf5be9f4bcd479989e6a24d142094d34d552daa"
#define MIKA_MODEL_SHA256 "3f30525381d72246b7f99e49b6cb66b249cf1b990c6c3d0e031a7765735f513e"
#define MIKA_MODEL_BYTES UINT64_C(279114080)
#define MIKA_MODEL_URL "https://huggingface.co/handy-computer/granite-speech-5.0-470m-turboctc-gguf/resolve/" MIKA_MODEL_REVISION "/" MIKA_MODEL_FILE

/* HTTPS only; does not replace destination until the entire payload is verified. */
int mika_model_download(const char *url, const char *destination, uint64_t expected_bytes,
                        const char *expected_sha256, MikaTerminal *terminal);
int mika_model_ensure(MikaTerminal *terminal, char **model_path);

#endif

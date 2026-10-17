#ifndef MIKA_FULLSTOP_H
#define MIKA_FULLSTOP_H

#include "punctuation.h"
#if defined(_WIN32) && defined(MIKA_FULLSTOP_BUILD)
#define MIKA_FULLSTOP_API __declspec(dllexport)
#elif defined(__GNUC__)
#define MIKA_FULLSTOP_API __attribute__((visibility("default")))
#else
#define MIKA_FULLSTOP_API
#endif
#ifdef __cplusplus
extern "C" {
#endif

typedef struct MikaFullstop MikaFullstop;
/* Private versioned-by-source ABI. UTF-8 paths; exceptions stay inside the
 * implementation. Allocations returned by this module must be freed here. */
MIKA_FULLSTOP_API MikaFullstop *MikaFullstopOpen(const char *model, const char *vocab);
MIKA_FULLSTOP_API void MikaFullstopClose(MikaFullstop *model);
MIKA_FULLSTOP_API int MikaFullstopApply(MikaFullstop *model, const char *raw,
    MikaPunctuationCancelled cancelled, void *userdata, char **out);
MIKA_FULLSTOP_API void MikaFullstopFreeText(char *text);

#ifdef __cplusplus
}
#endif
#endif

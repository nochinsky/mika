/* Development probe: text files are explicit test inputs, never microphone audio.
 * Exit 0 formatted, 1 raw fallback, 130 cancelled, 2 invalid probe input. */
#include "punctuation.h"
#include "platform.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#else
#include <sys/resource.h>
#endif

static uint64_t peak_rss_kib(void)
{
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS memory;
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &memory, sizeof(memory))) { return 0; }
    return (uint64_t)(memory.PeakWorkingSetSize / 1024u);
#else
    struct rusage usage;
    return getrusage(RUSAGE_SELF, &usage) == 0 ? (uint64_t)usage.ru_maxrss : 0;
#endif
}

struct Cancel { unsigned calls, at; };
static int cancelled(void *userdata)
{
    struct Cancel *cancel = userdata;
    return ++cancel->calls == cancel->at;
}

static int probe(int argc, char **argv)
{
    mika_console_utf8();
    if (argc < 3 || argc > 4 || mika_platform_init()) { return 2; }
    FILE *file = mika_fopen(argv[2], "rb");
    char *raw = calloc(MIKA_PUNCTUATION_MAX_INPUT + 2u, 1);
    if (!file || !raw) { if (file) { fclose(file); } free(raw); return 2; }
    size_t size = fread(raw, 1, MIKA_PUNCTUATION_MAX_INPUT + 1u, file);
    int bad = ferror(file) || size > MIKA_PUNCTUATION_MAX_INPUT || memchr(raw, 0, size) != NULL;
    fclose(file);
    if (bad) { free(raw); return 2; }
    struct Cancel cancel = {0, argc == 4 ? (unsigned)strtoul(argv[3], NULL, 10) : 0};
    char *out = NULL;
    double start = mika_now();
    int result = mika_punctuation_run(argv[1], raw, cancelled, &cancel, &out);
    fprintf(stderr, "format_ms=%.3f result=%d peak_rss_kib=%" PRIu64 " cancel_calls=%u\n",
            (mika_now() - start) * 1000.0, result, peak_rss_kib(), cancel.calls);
    if (result != 130 && (puts(out ? out : raw) == EOF || fflush(stdout))) { result = 2; }
    free(out);
    free(raw);
    return result;
}

#ifdef _WIN32
int wmain(int argc, wchar_t **wide)
{
    char **argv = calloc((size_t)argc, sizeof(*argv));
    if (!argv) { return 2; }
    int result = 2;
    for (int i = 0; i < argc; ++i) {
        int n = WideCharToMultiByte(CP_UTF8, 0, wide[i], -1, NULL, 0, NULL, NULL);
        argv[i] = n > 0 ? malloc((size_t)n) : NULL;
        if (!argv[i] || !WideCharToMultiByte(CP_UTF8, 0, wide[i], -1, argv[i], n, NULL, NULL)) { goto done; }
    }
    result = probe(argc, argv);
done:
    for (int i = 0; i < argc; ++i) { free(argv[i]); }
    free(argv);
    return result;
}
#else
int main(int argc, char **argv) { return probe(argc, argv); }
#endif

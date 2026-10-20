#ifndef MIKA_TEST_PEAK_RSS_H
#define MIKA_TEST_PEAK_RSS_H

#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#else
#include <sys/resource.h>
#endif

/* Whole-process peak, not incremental model RAM. Darwin reports bytes while
 * Linux reports KiB; both developer probes must expose the same KiB field. */
static uint64_t peak_rss_kib(void)
{
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS memory;
    if (!GetProcessMemoryInfo(GetCurrentProcess(), &memory, sizeof(memory))) { return 0; }
    return (uint64_t)(memory.PeakWorkingSetSize / 1024u);
#else
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) { return 0; }
#ifdef __APPLE__
    return (uint64_t)usage.ru_maxrss / 1024u;
#else
    return (uint64_t)usage.ru_maxrss;
#endif
#endif
}

#endif

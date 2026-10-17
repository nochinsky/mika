#ifndef MIKA_PLATFORM_H
#define MIKA_PLATFORM_H

#include <stdint.h>
#include <stdio.h>

typedef struct MikaTerminal MikaTerminal;
typedef struct MikaFileLock MikaFileLock;

enum { MIKA_KEY_TIMEOUT = -1, MIKA_KEY_ERROR = -2 };

/* Encoding only: safe for --help without an interactive console. Restored at exit. */
void mika_console_utf8(void);
int mika_platform_init(void);
int mika_cancelled(void *unused);
double mika_now(void);
int mika_stderr_is_terminal(void);
/* Transient ASCII status on stderr only; silent when redirected. Clear before diagnostics. */
void mika_status_show(const char *message);
void mika_status_clear(void);
MikaTerminal *mika_terminal_open(void);
int mika_terminal_key(MikaTerminal *terminal, unsigned timeout_ms);
void mika_terminal_discard_input(MikaTerminal *terminal);
void mika_terminal_close(MikaTerminal *terminal);

/* All application paths are UTF-8, including on Windows. Caller frees strings. */
char *mika_path_join(const char *directory, const char *name);
char *mika_model_directory(void);
int mika_mkdirs(const char *directory);
FILE *mika_fopen(const char *path, const char *mode);
int mika_file_size(FILE *file, uint64_t *size);
FILE *mika_temp_file(const char *destination, char **path);
int mika_flush_file(FILE *file);
int mika_remove_file(const char *path);
int mika_replace_file(const char *source, const char *destination);
MikaFileLock *mika_lock_acquire(const char *directory);
void mika_lock_release(MikaFileLock *lock);

#endif

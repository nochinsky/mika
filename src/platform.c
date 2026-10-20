#include "platform.h"

#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>
#include <direct.h>
#include <fcntl.h>
#include <io.h>
#include <share.h>

static volatile LONG interrupted;
static UINT original_output_codepage;
static int console_prepared;

static void restore_codepage(void)
{
    if (original_output_codepage) { SetConsoleOutputCP(original_output_codepage); }
}

struct MikaTerminal { HANDLE input; DWORD original_mode; };
struct MikaFileLock { HANDLE file; };

static BOOL WINAPI console_interrupt(DWORD type)
{
    if (type == CTRL_C_EVENT || type == CTRL_BREAK_EVENT) {
        InterlockedExchange(&interrupted, 1);
        return TRUE;
    }
    return FALSE;
}

static wchar_t *wide_path(const char *text)
{
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, NULL, 0);
    if (!length) { errno = EINVAL; return NULL; }
    wchar_t *wide = malloc((size_t)length * sizeof(*wide));
    if (!wide) { return NULL; }
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide, length)) {
        free(wide);
        return NULL;
    }
    return wide;
}

void mika_console_utf8(void)
{
    if (console_prepared) { return; }
    console_prepared = 1;
    original_output_codepage = GetConsoleOutputCP();
    if (original_output_codepage) {
        SetConsoleOutputCP(CP_UTF8);
        atexit(restore_codepage);
    }
}

int mika_platform_init(void)
{
    mika_console_utf8();
    return SetConsoleCtrlHandler(console_interrupt, TRUE) ? 0 : -1;
}

int mika_cancelled(void *unused)
{
    (void)unused;
    return InterlockedCompareExchange(&interrupted, 0, 0) != 0;
}

double mika_now(void)
{
    LARGE_INTEGER now, frequency;
    QueryPerformanceCounter(&now);
    QueryPerformanceFrequency(&frequency);
    return (double)now.QuadPart / (double)frequency.QuadPart;
}

int mika_stderr_is_terminal(void)
{
    DWORD mode;
    return GetConsoleMode((HANDLE)_get_osfhandle(_fileno(stderr)), &mode) != 0;
}

static unsigned status_columns(void)
{
    CONSOLE_SCREEN_BUFFER_INFO info;
    HANDLE output = (HANDLE)_get_osfhandle(_fileno(stderr));
    return GetConsoleScreenBufferInfo(output, &info)
        ? (unsigned)(info.srWindow.Right - info.srWindow.Left + 1) : 80;
}
static void status_lock(void) { _lock_file(stderr); }
static void status_unlock(void) { _unlock_file(stderr); }

MikaTerminal *mika_terminal_open(void)
{
    MikaTerminal *terminal = malloc(sizeof(*terminal));
    if (!terminal) { return NULL; }
    terminal->input = CreateFileW(L"CONIN$", GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (terminal->input == INVALID_HANDLE_VALUE ||
        !GetConsoleMode(terminal->input, &terminal->original_mode)) {
        if (terminal->input != INVALID_HANDLE_VALUE) { CloseHandle(terminal->input); }
        free(terminal);
        return NULL;
    }
    DWORD mode = terminal->original_mode;
    mode &= ~(DWORD)(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT | ENABLE_QUICK_EDIT_MODE);
    mode |= ENABLE_PROCESSED_INPUT | ENABLE_EXTENDED_FLAGS;
    if (!SetConsoleMode(terminal->input, mode)) {
        CloseHandle(terminal->input);
        free(terminal);
        return NULL;
    }
    return terminal;
}

int mika_terminal_key(MikaTerminal *terminal, unsigned timeout_ms)
{
    DWORD wait = WaitForSingleObject(terminal->input, timeout_ms);
    if (wait == WAIT_TIMEOUT) { return MIKA_KEY_TIMEOUT; }
    if (wait != WAIT_OBJECT_0) { return MIKA_KEY_ERROR; }
    do {
        INPUT_RECORD record;
        DWORD count = 0;
        if (!ReadConsoleInputW(terminal->input, &record, 1, &count)) { return MIKA_KEY_ERROR; }
        if (count && record.EventType == KEY_EVENT && record.Event.KeyEvent.bKeyDown) {
            wchar_t ch = record.Event.KeyEvent.uChar.UnicodeChar;
            if (ch == L'\r') { return '\n'; }
            if (ch > 0 && ch < 128) { return (int)ch; }
        }
    } while (WaitForSingleObject(terminal->input, 0) == WAIT_OBJECT_0);
    return MIKA_KEY_TIMEOUT;
}

void mika_terminal_discard_input(MikaTerminal *terminal)
{
    FlushConsoleInputBuffer(terminal->input);
}

void mika_terminal_close(MikaTerminal *terminal)
{
    if (terminal) {
        SetConsoleMode(terminal->input, terminal->original_mode);
        CloseHandle(terminal->input);
        free(terminal);
    }
}

char *mika_model_directory(void)
{
    PWSTR wide = NULL;
    if (FAILED(SHGetKnownFolderPath(&FOLDERID_LocalAppData, 0, NULL, &wide))) { return NULL; }
    int length = WideCharToMultiByte(CP_UTF8, 0, wide, -1, NULL, 0, NULL, NULL);
    char *base = length > 0 ? malloc((size_t)length) : NULL;
    if (base && !WideCharToMultiByte(CP_UTF8, 0, wide, -1, base, length, NULL, NULL)) {
        free(base);
        base = NULL;
    }
    CoTaskMemFree(wide);
    char *path = base ? mika_path_join(base, "Mika/models") : NULL;
    free(base);
    return path;
}

FILE *mika_fopen(const char *path, const char *mode)
{
    wchar_t *wide = wide_path(path), *wide_mode = wide_path(mode);
    FILE *file = wide && wide_mode ? _wfopen(wide, wide_mode) : NULL;
    free(wide_mode);
    free(wide);
    return file;
}

static int make_directory(const char *path)
{
    wchar_t *wide = wide_path(path);
    if (!wide) { return -1; }
    int result = _wmkdir(wide);
    free(wide);
    return result;
}

static int is_directory(const char *path)
{
    wchar_t *wide = wide_path(path);
    struct _stat64 info;
    int result = wide && _wstat64(wide, &info) == 0 && (info.st_mode & _S_IFMT) == _S_IFDIR;
    free(wide);
    return result;
}

int mika_file_size(FILE *file, uint64_t *size)
{
    struct _stat64 info;
    if (_fstat64(_fileno(file), &info) != 0 ||
        (info.st_mode & _S_IFMT) != _S_IFREG || info.st_size < 0) { return -1; }
    *size = (uint64_t)info.st_size;
    return 0;
}

FILE *mika_temp_file(const char *destination, char **path)
{
    size_t length = strlen(destination) + 80;
    *path = malloc(length);
    if (!*path) { return NULL; }
    for (unsigned i = 0; i < 100; ++i) {
        snprintf(*path, length, "%s.part.%lu.%llu.%u", destination,
                 (unsigned long)GetCurrentProcessId(), (unsigned long long)GetTickCount64(), i);
        wchar_t *wide = wide_path(*path);
        if (!wide) { break; }
        int fd = -1;
        errno_t result = _wsopen_s(&fd, wide, _O_CREAT | _O_EXCL | _O_WRONLY | _O_BINARY,
                                  _SH_DENYRW, _S_IREAD | _S_IWRITE);
        free(wide);
        if (!result) {
            FILE *file = _fdopen(fd, "wb");
            if (file) { return file; }
            _close(fd);
            mika_remove_file(*path);
            break;
        }
        if (result != EEXIST) { break; }
    }
    free(*path);
    *path = NULL;
    return NULL;
}

int mika_flush_file(FILE *file)
{
    if (fflush(file) != 0) { return -1; }
    return _commit(_fileno(file));
}

int mika_remove_file(const char *path)
{
    wchar_t *wide = wide_path(path);
    int result = wide ? _wremove(wide) : -1;
    free(wide);
    return result;
}

int mika_replace_file(const char *source, const char *destination)
{
    wchar_t *from = wide_path(source), *to = wide_path(destination);
    int result = from && to && MoveFileExW(from, to,
        MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) ? 0 : -1;
    free(to);
    free(from);
    return result;
}

MikaFileLock *mika_lock_acquire(const char *directory)
{
    char *path = mika_path_join(directory, ".download.lock");
    wchar_t *wide = path ? wide_path(path) : NULL;
    MikaFileLock *lock = wide ? malloc(sizeof(*lock)) : NULL;
    free(path);
    if (!lock) { free(wide); return NULL; }
    lock->file = CreateFileW(wide, GENERIC_READ | GENERIC_WRITE, 0, NULL,
                             OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    free(wide);
    if (lock->file == INVALID_HANDLE_VALUE) { free(lock); return NULL; }
    return lock;
}

void mika_lock_release(MikaFileLock *lock)
{
    if (lock) { CloseHandle(lock->file); free(lock); }
}

#else
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/file.h>
#include <sys/ioctl.h>
#ifdef __APPLE__
#include <sys/select.h>
#endif
#include <termios.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;
struct MikaTerminal { int fd; struct termios original_mode; };
struct MikaFileLock { int fd; };

static void interrupt_handler(int signal_number) { interrupted = signal_number; }
void mika_console_utf8(void) {}

int mika_platform_init(void)
{
    struct sigaction action;
    memset(&action, 0, sizeof(action));
    action.sa_handler = interrupt_handler;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) || sigaction(SIGTERM, &action, NULL)) { return -1; }
    /* A closed output pipe must become EPIPE, not kill us with a raw terminal.
       This also protects diagnostics and HTTPS writes before normal cleanup. */
    action.sa_handler = SIG_IGN;
    return sigaction(SIGPIPE, &action, NULL);
}

int mika_cancelled(void *unused) { (void)unused; return interrupted != 0; }

double mika_now(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
}

int mika_stderr_is_terminal(void) { return isatty(STDERR_FILENO); }

static unsigned status_columns(void)
{
    struct winsize size;
    return ioctl(STDERR_FILENO, TIOCGWINSZ, &size) == 0 && size.ws_col ? size.ws_col : 80;
}
static void status_lock(void) { flockfile(stderr); }
static void status_unlock(void) { funlockfile(stderr); }

MikaTerminal *mika_terminal_open(void)
{
    MikaTerminal *terminal = malloc(sizeof(*terminal));
    if (!terminal) { return NULL; }
    terminal->fd = open("/dev/tty", O_RDWR | O_NOCTTY | O_CLOEXEC | O_NONBLOCK);
    if (terminal->fd < 0 || tcgetattr(terminal->fd, &terminal->original_mode) != 0) {
        if (terminal->fd >= 0) { close(terminal->fd); }
        free(terminal);
        return NULL;
    }
    struct termios mode = terminal->original_mode;
    mode.c_lflag &= (tcflag_t)~(ICANON | ECHO | IEXTEN);
    mode.c_lflag |= ISIG;
    mode.c_iflag &= (tcflag_t)~(IXON | ICRNL);
    /* With VMIN=0 Darwin can report an empty read as immediately ready.
       Require one byte for readiness; O_NONBLOCK still prevents a raced read. */
    mode.c_cc[VMIN] = 1;
    mode.c_cc[VTIME] = 0;
    if (tcsetattr(terminal->fd, TCSANOW, &mode) != 0) {
        close(terminal->fd);
        free(terminal);
        return NULL;
    }
    return terminal;
}

int mika_terminal_key(MikaTerminal *terminal, unsigned timeout_ms)
{
#ifdef __APPLE__
    /* select is supported for Darwin terminal devices, including /dev/tty. */
    if (terminal->fd >= FD_SETSIZE) { return MIKA_KEY_ERROR; }
    fd_set readable;
    FD_ZERO(&readable);
    FD_SET(terminal->fd, &readable);
    struct timeval wait = {(time_t)(timeout_ms / 1000u), (suseconds_t)((timeout_ms % 1000u) * 1000u)};
    int result = select(terminal->fd + 1, &readable, NULL, NULL, &wait);
#else
    struct pollfd item = {terminal->fd, POLLIN, 0};
    int result = poll(&item, 1, (int)timeout_ms);
#endif
    if (result < 0) { return errno == EINTR ? MIKA_KEY_TIMEOUT : MIKA_KEY_ERROR; }
    if (!result) { return MIKA_KEY_TIMEOUT; }
#ifndef __APPLE__
    if (item.revents & (POLLERR | POLLHUP | POLLNVAL)) { return MIKA_KEY_ERROR; }
#endif
    unsigned char key;
    ssize_t bytes = read(terminal->fd, &key, 1);
    if (bytes < 0 && (errno == EINTR || errno == EAGAIN)) { return MIKA_KEY_TIMEOUT; }
    if (bytes != 1) { return MIKA_KEY_ERROR; }
    return key == '\r' ? '\n' : key;
}

void mika_terminal_discard_input(MikaTerminal *terminal) { tcflush(terminal->fd, TCIFLUSH); }

void mika_terminal_close(MikaTerminal *terminal)
{
    if (terminal) {
        while (tcsetattr(terminal->fd, TCSAFLUSH, &terminal->original_mode) != 0 && errno == EINTR) {}
        close(terminal->fd);
        free(terminal);
    }
}

char *mika_model_directory(void)
{
    const char *home = getenv("HOME");
#ifdef __APPLE__
    return home && home[0] == '/' ? mika_path_join(home, "Library/Application Support/Mika/models") : NULL;
#else
    const char *data = getenv("XDG_DATA_HOME");
    if (data && data[0] == '/') { return mika_path_join(data, "mika/models"); }
    return home && home[0] == '/' ? mika_path_join(home, ".local/share/mika/models") : NULL;
#endif
}

FILE *mika_fopen(const char *path, const char *mode)
{
    if (strcmp(mode, "rb") != 0) { return fopen(path, mode); }
    /* Reject special files without blocking on a FIFO masquerading as a model. */
    int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) { return NULL; }
    struct stat info;
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode)) {
        close(fd);
        errno = EINVAL;
        return NULL;
    }
    FILE *file = fdopen(fd, mode);
    if (!file) { close(fd); }
    return file;
}
static int make_directory(const char *path) { return mkdir(path, 0700); }
static int is_directory(const char *path)
{
    struct stat info;
    return stat(path, &info) == 0 && S_ISDIR(info.st_mode);
}

int mika_file_size(FILE *file, uint64_t *size)
{
    struct stat info;
    if (fstat(fileno(file), &info) != 0 || !S_ISREG(info.st_mode) || info.st_size < 0) { return -1; }
    *size = (uint64_t)info.st_size;
    return 0;
}

FILE *mika_temp_file(const char *destination, char **path)
{
    size_t length = strlen(destination) + sizeof(".part.XXXXXX");
    *path = malloc(length);
    if (!*path) { return NULL; }
    snprintf(*path, length, "%s.part.XXXXXX", destination);
    int fd = mkstemp(*path);
    if (fd >= 0) {
        FILE *file = fdopen(fd, "wb");
        if (file) { return file; }
        close(fd);
        unlink(*path);
    }
    free(*path);
    *path = NULL;
    return NULL;
}

int mika_flush_file(FILE *file)
{
    if (fflush(file) != 0) { return -1; }
    return fsync(fileno(file));
}

int mika_remove_file(const char *path) { return unlink(path); }
int mika_replace_file(const char *source, const char *destination) { return rename(source, destination); }

MikaFileLock *mika_lock_acquire(const char *directory)
{
    char *path = mika_path_join(directory, ".download.lock");
    if (!path) { return NULL; }
    int fd = open(path, O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
    free(path);
    if (fd < 0) { return NULL; }
    if (flock(fd, LOCK_EX | LOCK_NB) != 0) { close(fd); return NULL; }
    MikaFileLock *lock = malloc(sizeof(*lock));
    if (!lock) { close(fd); return NULL; }
    lock->fd = fd;
    return lock;
}

void mika_lock_release(MikaFileLock *lock)
{
    if (lock) { close(lock->fd); free(lock); }
}
#endif

/* Plain carriage returns work in classic Windows consoles and TERM=dumb too.
 * Leave one column unused to avoid wrapping; never emit control bytes to a log. */
static unsigned status_width;

static void status_erase(void)
{
    unsigned columns = status_columns();
    unsigned width = columns ? columns - 1 : 0;
    if (width > status_width) { width = status_width; }
    if (status_width) { fprintf(stderr, "\r%*s\r", (int)width, ""); }
    status_width = 0;
}

void mika_status_show(const char *message)
{
    if (!mika_stderr_is_terminal()) { return; }
    status_lock();
    status_erase();
    unsigned columns = status_columns();
    size_t length = strlen(message);
    if (length >= columns) { length = columns ? columns - 1 : 0; }
    fprintf(stderr, "%.*s", (int)length, message);
    status_width = (unsigned)length;
    fflush(stderr);
    status_unlock();
}

void mika_status_clear(void)
{
    status_lock();
    status_erase();
    fflush(stderr);
    status_unlock();
}

char *mika_path_join(const char *directory, const char *name)
{
    size_t left = strlen(directory), right = strlen(name);
    if (right > SIZE_MAX - 2 || left > SIZE_MAX - right - 2) { return NULL; }
    char *path = malloc(left + right + 2);
    if (!path) { return NULL; }
    memcpy(path, directory, left);
    int separated = left && directory[left - 1] == '/';
#ifdef _WIN32
    separated = separated || (left && directory[left - 1] == '\\');
#endif
    if (left && !separated) { path[left++] = '/'; }
    memcpy(path + left, name, right + 1);
    return path;
}

int mika_mkdirs(const char *directory)
{
    if (make_directory(directory) == 0) { return 0; }
    if (errno == EEXIST) { return is_directory(directory) ? 0 : -1; }
    if (errno != ENOENT) { return -1; }
    size_t length = strlen(directory);
    char *parent = malloc(length + 1);
    if (!parent) { return -1; }
    memcpy(parent, directory, length + 1);
    char *separator = strrchr(parent, '/');
#ifdef _WIN32
    char *backslash = strrchr(parent, '\\');
    if (backslash && (!separator || backslash > separator)) { separator = backslash; }
#endif
    if (!separator || separator == parent) { free(parent); return -1; }
    *separator = '\0';
    int result = mika_mkdirs(parent);
    free(parent);
    if (result != 0) { return -1; }
    if (make_directory(directory) == 0) { return 0; }
    return errno == EEXIST && is_directory(directory) ? 0 : -1;
}

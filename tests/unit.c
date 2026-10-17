#include "model.h"
#include "pcm.h"
#include "platform.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
#include <signal.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #condition); return 1; \
} } while (0)

static const char empty_sha[] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
static const char abc_sha[] = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
static const char million_sha[] = "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0";

static int pcm_tests(void)
{
    MikaPcm pcm;
    CHECK(mika_pcm_init(&pcm, 4) == 0);
    float input[] = {0.1f, 0.2f, 0.3f, 0.4f, 0.5f};
    mika_pcm_append(&pcm, input, 2);
    CHECK(mika_atomic_get(&pcm.frames) == 2);
    CHECK(pcm.samples[0] == input[0] && pcm.samples[1] == input[1]);
    mika_pcm_append(&pcm, input + 2, 3);
    CHECK(mika_atomic_get(&pcm.frames) == 4);
    CHECK(pcm.samples[2] == input[2] && pcm.samples[3] == input[3]);
    mika_pcm_append(&pcm, input, 5);
    CHECK(mika_atomic_get(&pcm.frames) == 4 && pcm.samples[3] == input[3]);
    mika_pcm_free(&pcm);
    CHECK(mika_pcm_init(&pcm, 1) == 0);
    mika_pcm_append(&pcm, NULL, 0);
    CHECK(mika_atomic_get(&pcm.failed) == 0);
    mika_pcm_append(&pcm, NULL, 1);
    CHECK(mika_atomic_get(&pcm.failed) == 1 && mika_atomic_get(&pcm.frames) == 0);
    mika_pcm_free(&pcm);
    CHECK(mika_pcm_init(&pcm, 0) == 1);
    CHECK(mika_pcm_init(&pcm, MIKA_MAX_FRAMES + 1) == 1);
    return 0;
}

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    CHECK(mika_platform_init() == 0);
    CHECK(pcm_tests() == 0);
    const char *directory = argv[1];
    CHECK(mika_mkdirs(directory) == 0);
    CHECK(mika_mkdirs(directory) == 0);
    char *path = mika_path_join(directory, "checksum - unicode \xc3\xa9.txt");
    CHECK(path != NULL);
    FILE *file = mika_fopen(path, "wb");
    CHECK(file != NULL && fclose(file) == 0);
    CHECK(mika_model_verify(path, 0, empty_sha) == MIKA_MODEL_VALID);
    file = mika_fopen(path, "wb");
    CHECK(file != NULL);
    CHECK(fwrite("abc", 1, 3, file) == 3 && fclose(file) == 0);
    CHECK(mika_model_verify(path, 3, abc_sha) == MIKA_MODEL_VALID);
    CHECK(mika_model_verify(path, 2, abc_sha) == MIKA_MODEL_INVALID);
    CHECK(mika_model_verify(path, 4, abc_sha) == MIKA_MODEL_INVALID);
    CHECK(mika_model_verify(path, 3, empty_sha) == MIKA_MODEL_INVALID);
    CHECK(mika_mkdirs(path) != 0);
    file = mika_fopen(path, "wb");
    CHECK(file != NULL);
    char chunk[10000];
    memset(chunk, 'a', sizeof(chunk));
    for (unsigned i = 0; i < 100; ++i) { CHECK(fwrite(chunk, 1, sizeof(chunk), file) == sizeof(chunk)); }
    CHECK(fclose(file) == 0);
    CHECK(mika_model_verify(path, 1000000, million_sha) == MIKA_MODEL_VALID);

    MikaFileLock *first = mika_lock_acquire(directory);
    CHECK(first != NULL);
    MikaFileLock *second = mika_lock_acquire(directory);
    CHECK(second == NULL);
    mika_lock_release(first);
    second = mika_lock_acquire(directory);
    CHECK(second != NULL);
    mika_lock_release(second);

    char *temporary = NULL;
    FILE *temp = mika_temp_file(path, &temporary);
    CHECK(temp != NULL && temporary != NULL);
#ifndef _WIN32
    struct stat info;
    CHECK(stat(temporary, &info) == 0 && (info.st_mode & 0077) == 0);
#endif
    CHECK(fwrite("abc", 1, 3, temp) == 3);
    CHECK(mika_flush_file(temp) == 0 && fclose(temp) == 0);
    CHECK(mika_replace_file(temporary, path) == 0);
    CHECK(mika_model_verify(path, 3, abc_sha) == MIKA_MODEL_VALID);
    CHECK(mika_model_verify(temporary, 3, abc_sha) == MIKA_MODEL_INVALID);
    free(temporary);

    /* Rejected protocols must leave a previously valid destination untouched. */
    CHECK(mika_model_download("http://127.0.0.1:1/no-network", path, 3, abc_sha, NULL) == 1);
    CHECK(mika_model_verify(path, 3, abc_sha) == MIKA_MODEL_VALID);
    CHECK(mika_model_download("file:///etc/passwd", path, 3, abc_sha, NULL) == 1);
    CHECK(mika_model_verify(path, 3, abc_sha) == MIKA_MODEL_VALID);
#ifndef _WIN32
    char *special = mika_path_join(directory, "special");
    CHECK(special != NULL);
    unlink(special);
    CHECK(mkfifo(special, 0600) == 0);
    CHECK(mika_model_verify(special, 3, abc_sha) == MIKA_MODEL_IO_ERROR);
    CHECK(unlink(special) == 0);
    CHECK(symlink(path, special) == 0);
    CHECK(mika_model_verify(special, 3, abc_sha) == MIKA_MODEL_IO_ERROR);
    CHECK(unlink(special) == 0);
    free(special);
    CHECK(raise(SIGINT) == 0);
    CHECK(mika_model_verify(path, 3, abc_sha) == 130);
    CHECK(mika_model_download("https://127.0.0.1:1", path, 3, abc_sha, NULL) == 130);
#endif
    CHECK(mika_remove_file(path) == 0);
    free(path);
    puts("PASS: checksums, bounds, private temp files, publication, locks, protocol policy, cancellation");
    return 0;
}

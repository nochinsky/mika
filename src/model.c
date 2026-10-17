#include "model.h"

#include <curl/curl.h>
#include <openssl/evp.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static void hex_digest(const unsigned char *digest, char hex[65])
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
        hex_digest(digest, hex);
        result = strcmp(hex, expected_sha256) == 0 ? MIKA_MODEL_VALID : MIKA_MODEL_INVALID;
    }
done:
    EVP_MD_CTX_free(hash);
    if (fclose(file) != 0 && result == MIKA_MODEL_VALID) { result = MIKA_MODEL_IO_ERROR; }
    return result;
}

struct Download {
    FILE *file;
    EVP_MD_CTX *hash;
    MikaTerminal *terminal;
    uint64_t bytes, limit;
    int cancelled;
    int last_percent;
    int show_progress;
};

static size_t download_write(char *data, size_t size, size_t count, void *userdata)
{
    struct Download *download = userdata;
    if (size && count > SIZE_MAX / size) { return 0; }
    size_t bytes = size * count;
    if (mika_cancelled(NULL) || (uint64_t)bytes > download->limit - download->bytes) { return 0; }
    size_t written = fwrite(data, 1, bytes, download->file);
    download->bytes += (uint64_t)written;
    if (EVP_DigestUpdate(download->hash, data, written) != 1) { return 0; }
    return written;
}

static int download_progress(void *userdata, curl_off_t total, curl_off_t current,
                              curl_off_t upload_total, curl_off_t uploaded)
{
    (void)total; (void)current; (void)upload_total; (void)uploaded;
    struct Download *download = userdata;
    if (download->terminal && mika_terminal_key(download->terminal, 0) == 27) {
        download->cancelled = 1;
    }
    if (mika_cancelled(NULL) || download->cancelled) { return 1; }
    int percent = download->limit ? (int)(100.0 * (double)download->bytes / (double)download->limit) : 0;
    if (download->show_progress && percent != download->last_percent) {
        fprintf(stderr, "\r  Downloading model: %3d%%", percent);
        fflush(stderr);
        download->last_percent = percent;
    }
    return 0;
}

int mika_model_download(const char *url, const char *destination, uint64_t expected_bytes,
                        const char *expected_sha256, MikaTerminal *terminal)
{
    int result = 1;
    char *temporary = NULL;
    struct Download download = {0};
    download.limit = expected_bytes;
    download.terminal = terminal;
    download.last_percent = -1;
    download.show_progress = mika_stderr_is_terminal();
    if (mika_cancelled(NULL)) { return 130; }
    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        fputs("mika: cannot initialize HTTPS downloads.\n", stderr);
        return 1;
    }
    CURL *curl = curl_easy_init();
    download.hash = EVP_MD_CTX_new();
    download.file = mika_temp_file(destination, &temporary);
    if (!curl || !download.hash || !download.file ||
        EVP_DigestInit_ex(download.hash, EVP_sha256(), NULL) != 1) {
        fputs("mika: cannot create a private model download file.\n", stderr);
        goto done;
    }
    char error[CURL_ERROR_SIZE] = {0};
    CURLcode setting = CURLE_OK;
#define SET_OPTION(option, value) do { \
    CURLcode status = curl_easy_setopt(curl, option, value); \
    if (status != CURLE_OK) { setting = status; } \
} while (0)
    SET_OPTION(CURLOPT_URL, url);
    SET_OPTION(CURLOPT_ERRORBUFFER, error);
    SET_OPTION(CURLOPT_PROTOCOLS_STR, "https");
    SET_OPTION(CURLOPT_REDIR_PROTOCOLS_STR, "https");
    SET_OPTION(CURLOPT_FOLLOWLOCATION, 1L);
    SET_OPTION(CURLOPT_MAXREDIRS, 5L);
    SET_OPTION(CURLOPT_FAILONERROR, 1L);
    SET_OPTION(CURLOPT_SSL_VERIFYPEER, 1L);
    SET_OPTION(CURLOPT_SSL_VERIFYHOST, 2L);
    /* Standard curl CLI convention, useful behind a privately trusted proxy. */
    const char *ca_bundle = getenv("CURL_CA_BUNDLE");
    if (ca_bundle && ca_bundle[0]) { SET_OPTION(CURLOPT_CAINFO, ca_bundle); }
#ifndef _WIN32
    else {
        /* Static release dependencies must use the HOST trust store, not a
         * build runner's vcpkg prefix. These cover Arch, Debian/Ubuntu and Fedora. */
        const char *paths[] = {"/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem",
                               "/etc/pki/tls/certs/ca-bundle.crt"};
        for (size_t i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i) {
            FILE *certificates = fopen(paths[i], "rb");
            if (certificates) {
                fclose(certificates);
                SET_OPTION(CURLOPT_CAINFO, paths[i]);
                break;
            }
        }
    }
#endif
    SET_OPTION(CURLOPT_CONNECTTIMEOUT, 30L);
    SET_OPTION(CURLOPT_LOW_SPEED_LIMIT, 1024L);
    SET_OPTION(CURLOPT_LOW_SPEED_TIME, 30L);
    SET_OPTION(CURLOPT_TIMEOUT, 3600L);
    SET_OPTION(CURLOPT_NOSIGNAL, 1L);
    SET_OPTION(CURLOPT_MAXFILESIZE_LARGE, (curl_off_t)expected_bytes);
    SET_OPTION(CURLOPT_USERAGENT, "mika/0.1.0");
    SET_OPTION(CURLOPT_WRITEFUNCTION, download_write);
    SET_OPTION(CURLOPT_WRITEDATA, &download);
    SET_OPTION(CURLOPT_NOPROGRESS, 0L);
    SET_OPTION(CURLOPT_XFERINFOFUNCTION, download_progress);
    SET_OPTION(CURLOPT_XFERINFODATA, &download);
#undef SET_OPTION
    if (setting != CURLE_OK) {
        fprintf(stderr, "mika: cannot configure HTTPS download: %s.\n", curl_easy_strerror(setting));
        goto done;
    }
    CURLcode transfer = curl_easy_perform(curl);
    if (download.show_progress) { fputc('\n', stderr); }
    if (mika_cancelled(NULL) || download.cancelled) { result = 130; goto done; }
    long response = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response);
    if (transfer != CURLE_OK || response != 200) {
        fprintf(stderr, "mika: download failed: %s (HTTP %ld).\n",
                error[0] ? error : curl_easy_strerror(transfer), response);
        goto done;
    }
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned digest_bytes = 0;
    char hex[65];
    if (EVP_DigestFinal_ex(download.hash, digest, &digest_bytes) != 1 || digest_bytes != 32) {
        fputs("mika: cannot finish the model checksum.\n", stderr);
        goto done;
    }
    hex_digest(digest, hex);
    if (download.bytes != expected_bytes || strcmp(hex, expected_sha256) != 0) {
        fputs("mika: model size or SHA-256 mismatch; download discarded.\n", stderr);
        goto done;
    }
    if (mika_flush_file(download.file) != 0) {
        fputs("mika: cannot flush the downloaded model to disk.\n", stderr);
        goto done;
    }
    int close_result = fclose(download.file);
    download.file = NULL;
    if (close_result != 0) {
        fputs("mika: cannot close the downloaded model file.\n", stderr);
        goto done;
    }
    if (mika_cancelled(NULL)) { result = 130; goto done; }
    if (mika_replace_file(temporary, destination) != 0) {
        fputs("mika: cannot publish the verified model in its data directory.\n", stderr);
        goto done;
    }
    result = 0;
done:
    if (download.file) { fclose(download.file); }
    if (temporary) { mika_remove_file(temporary); }
    free(temporary);
    EVP_MD_CTX_free(download.hash);
    curl_easy_cleanup(curl);
    curl_global_cleanup();
    return result;
}

int mika_model_ensure(MikaTerminal *terminal, char **model_path)
{
    *model_path = NULL;
    int result = 1;
    char *directory = mika_model_directory();
    char *path = directory ? mika_path_join(directory, MIKA_MODEL_FILE) : NULL;
    MikaFileLock *lock = NULL;
    if (!path) {
        fputs("mika: cannot resolve a writable per-user model directory.\n", stderr);
        goto done;
    }
    fputs("  Checking model...\n", stderr);
    int valid = mika_model_verify(path, MIKA_MODEL_BYTES, MIKA_MODEL_SHA256);
    if (valid == 130) { result = 130; goto done; }
    if (valid == MIKA_MODEL_VALID) { result = 0; goto done; }
    if (valid == MIKA_MODEL_IO_ERROR) {
        fprintf(stderr, "mika: cannot read model at %s. Check file permissions.\n", path);
        goto done;
    }
    fprintf(stderr, "  Mika needs its English speech model (279 MB).\n"
                    "  Location: %s\n"
                    "  Installation/replacement happens only after verification.\n"
                    "  Download now? [y/N] ", path);
    fflush(stderr);
    for (;;) {
        if (mika_cancelled(NULL)) { result = 130; goto done; }
        int key = mika_terminal_key(terminal, 100);
        if (key == MIKA_KEY_TIMEOUT) { continue; }
        if (key == MIKA_KEY_ERROR) {
            fputs("\nmika: lost the controlling terminal.\n", stderr);
            goto done;
        }
        if (key != 'y' && key != 'Y') {
            fputs("no\n", stderr);
            result = 130;
            goto done;
        }
        fputs("yes\n", stderr);
        break;
    }
    if (mika_mkdirs(directory) != 0) {
        fprintf(stderr, "mika: cannot create model directory: %s.\n", directory);
        goto done;
    }
    lock = mika_lock_acquire(directory);
    if (!lock) {
        fputs("mika: cannot lock the model directory; another Mika may be preparing it. Try again.\n", stderr);
        goto done;
    }
    /* Another process may have completed installation while we asked for consent. */
    valid = mika_model_verify(path, MIKA_MODEL_BYTES, MIKA_MODEL_SHA256);
    if (valid == 130) { result = 130; goto done; }
    if (valid == MIKA_MODEL_VALID) { result = 0; goto done; }
    fputs("  Downloading and verifying model; Ctrl+C or Esc cancels.\n", stderr);
    result = mika_model_download(MIKA_MODEL_URL, path, MIKA_MODEL_BYTES, MIKA_MODEL_SHA256, terminal);
    if (!result) { fputs("  Model ready.\n", stderr); }
done:
    mika_lock_release(lock);
    free(directory);
    if (!result) { *model_path = path; } else { free(path); }
    return result;
}

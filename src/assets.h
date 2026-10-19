#ifndef MIKA_ASSETS_H
#define MIKA_ASSETS_H

#ifdef __cplusplus
extern "C" {
#endif

/* Resolve a fixed bundled asset relative to the real executable, never cwd.
 * UTF-8 on every platform. Caller frees the result; NULL means path/allocation
 * failure. Only application-owned relative names belong in this interface. */
char *mika_asset_path(const char *relative);

#ifdef __cplusplus
}
#endif
#endif

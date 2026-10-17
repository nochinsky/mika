/* Metadata-only integration probe: enumerates inputs without opening a stream. */
#include "miniaudio.h"
#include <stdio.h>

int main(void)
{
    ma_context context;
    ma_result result = ma_context_init(NULL, 0, NULL, &context);
    if (result != MA_SUCCESS) { fprintf(stderr, "%s\n", ma_result_description(result)); return 1; }
    ma_device_info *devices = NULL;
    ma_uint32 count = 0;
    result = ma_context_get_devices(&context, NULL, NULL, &devices, &count);
    printf("Backend: %s\n", ma_get_backend_name(context.backend));
    for (ma_uint32 i = 0; result == MA_SUCCESS && i < count; ++i) {
        printf("Input: %s%s\n", devices[i].name, devices[i].isDefault ? " (default)" : "");
    }
    ma_context_uninit(&context);
    return result == MA_SUCCESS && count ? 0 : 1;
}

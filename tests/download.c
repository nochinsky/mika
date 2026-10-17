/* Test driver for the real downloader. Never installed with Mika. */
#include "model.h"
#include "platform.h"
#include <stdlib.h>

int main(int argc, char **argv)
{
    if (argc != 5 || mika_platform_init()) { return 2; }
    return mika_model_download(argv[1], argv[2], (uint64_t)strtoull(argv[3], NULL, 10), argv[4], NULL);
}

/* Test driver for the real downloader. Never installed with Mika. */
#include "model.h"
#include "platform.h"
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    int interactive = argc == 6 && strcmp(argv[5], "--terminal") == 0;
    if ((argc != 5 && !interactive) || mika_platform_init()) { return 2; }
    MikaTerminal *terminal = interactive ? mika_terminal_open() : NULL;
    if (interactive && !terminal) { return 1; }
    int result = mika_model_download(argv[1], argv[2], (uint64_t)strtoull(argv[3], NULL, 10), argv[4], terminal);
    mika_terminal_close(terminal);
    return result;
}

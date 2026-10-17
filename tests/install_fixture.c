/* Installer transaction fixture: no inference, networking, or microphone. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    (void)argc;
    if (getenv("MIKA_INSTALL_FIXTURE_FAIL_FINAL") &&
        (strstr(argv[0], "/app/bin/") || strstr(argv[0], "\\app\\bin\\"))) {
        return 42;
    }
    puts("mika 0.0.0");
    return 0;
}

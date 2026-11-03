#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
/* Host-only fault injection; use real fsync at every other boundary. */
int once_enable_fsync(int fd) {
    static unsigned calls;
    const char *value = getenv("ONCE_FAIL_FSYNC");
    if (value && ++calls == (unsigned)atoi(value)) {
        errno = EIO;
        return -1;
    }
    return fsync(fd);
}

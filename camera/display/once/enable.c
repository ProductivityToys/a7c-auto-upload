/* Explicit operator tool, never called by boot. Staging/hash verification is
 * performed by the USB operator before this tool. No reboot or media access. */
#include "protocol.h"
#include "platform.h"
#ifndef PRELOAD_PATH
#define PRELOAD_PATH "/etc/ld.so.preload"
#endif
#ifndef PRELOAD_PARENT
#define PRELOAD_PARENT "/etc"
#endif
#ifndef SETTING_PARENT
#define SETTING_PARENT "/setting"
#endif
#define MAX_FILE 8192
static char before[MAX_FILE + 1], current[MAX_FILE + 1], output[MAX_FILE + 256];

static int absent(const char *path) {
    int fd = open(path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
    if (fd >= 0) { close(fd); return 0; }
    return errno == ENOENT;
}
static int barrier(const char *path, int directory) {
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC |
                        (directory ? O_DIRECTORY : O_NONBLOCK));
    if (fd < 0) return 0;
    int rc = fsync(fd), c = close(fd);
    return !rc && !c;
}
static int storage(void) {
    const char *files[] = {SHIM_PATH, ENTRY_PATH, OBSERVER_PATH,
        ONCE_ROOT "/enable", ONCE_ROOT "/revoke", ONCE_ROOT "/preload.before"};
    for (unsigned i = 0; i < sizeof(files) / sizeof(files[0]); i++)
        if (!barrier(files[i], 0)) return 0;
    return barrier(ONCE_ROOT, 1) && barrier(SETTING_PARENT, 1) &&
           barrier(PRELOAD_PARENT, 1);
}
int main(int argc, char **argv) {
    if (argc != 2 || (!once_equal(argv[1], "--check-storage") &&
                      !once_equal(argv[1], "--enable"))) return 64;
    if (!storage()) return 2;
    if (once_equal(argv[1], "--check-storage")) return 0;
    if (!absent(ONCE_ROOT "/armed") || !absent(ONCE_ROOT "/spent") ||
        !absent(PRELOAD_PATH ".a7c-ui-new")) return 3;
    long n = once_read_file(ONCE_ROOT "/preload.before", before, sizeof(before));
    long cn = once_read_file(PRELOAD_PATH, current, sizeof(current));
    if (n < 0 || n > MAX_FILE || cn != n) return 3;
    before[n] = 0;
    for (long i = 0; i < n; i++) {
        if (!before[i] || current[i] != before[i]) return 3;
        /* Refuse any earlier experiment reference, not only an exact line. */
        if (once_prefix(before + i, ONCE_ROOT)) return 3;
    }
    unsigned length = (unsigned)n;
    for (unsigned i = 0; i < length; i++) output[i] = before[i];
    if (length && output[length - 1] != '\n') output[length++] = '\n';
    const char *line = SHIM_PATH "\n";
    for (unsigned i = 0; line[i]; i++) output[length++] = line[i];
    int fd = open(PRELOAD_PATH ".a7c-ui-new",
                  O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0644);
    if (fd < 0) return 4;
    int ok = once_write_all(fd, output, length);
    if (fsync(fd)) ok = 0;
    if (close(fd)) ok = 0;
    cn = once_read_file(PRELOAD_PATH, current, sizeof(current));
    if (cn != n) ok = 0;
    for (long i = 0; ok && i < n; i++) if (current[i] != before[i]) ok = 0;
    if (ok && rename(PRELOAD_PATH ".a7c-ui-new", PRELOAD_PATH)) ok = 0;
    if (ok && !barrier(PRELOAD_PARENT, 1)) ok = 0;
    if (!ok) return 4; /* No ticket, preserve staging/evidence for revoke. */
    fd = open(ONCE_ROOT "/armed",
              O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return 5;
    ok = once_write_all(fd, TICKET_VALUE, sizeof(TICKET_VALUE) - 1);
    if (fsync(fd)) ok = 0;
    if (close(fd)) ok = 0;
    if (ok && !barrier(ONCE_ROOT, 1)) ok = 0;
    if (!ok) {
        unlink(ONCE_ROOT "/armed");
        barrier(ONCE_ROOT, 1);
        return 5; /* Caller must run revoke and verify, even after unlink. */
    }
    return 0;
}

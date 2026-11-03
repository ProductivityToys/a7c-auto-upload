/* Recovery executable; only our ticket and preload line. No dlclose/kill/reboot.
 * Return 0: future loading disabled; existing mappings still require process exit.
 * Return 2: ticket/barrier failure; 3: preload read/ambiguity; 4: atomic replace failure. */
#include "protocol.h"
#include "platform.h"
#ifndef PRELOAD_PATH
#define PRELOAD_PATH "/etc/ld.so.preload"
#endif
#ifndef PRELOAD_PARENT
#define PRELOAD_PARENT "/etc"
#endif
#define MAX_FILE 8192
static char current[MAX_FILE + 1], before[MAX_FILE + 1], output[MAX_FILE + 1];
int main(int argc, char **argv) {
    if (argc != 2 || !once_equal(argv[1], "--disable")) return 64;
    if (unlink(ONCE_ROOT "/armed") && errno != ENOENT) return 2;
    int dir = open(ONCE_ROOT, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (dir >= 0) {
        int rc = fsync(dir);
        int c = close(dir);
        if (rc || c) return 2;
    } else if (errno != ENOENT) return 2;
    long n = once_read_file(PRELOAD_PATH, current, sizeof(current));
    if (n < 0 || n > MAX_FILE) return 3;
    long bn = once_read_file(ONCE_ROOT "/preload.before", before, sizeof(before));
    if (bn < 0 || bn > MAX_FILE) return 3;
    int length = once_remove_line(current, (unsigned)n, before, (unsigned)bn, output);
    if (length < 0) return 3;
    int same = length == n;
    for (int i = 0; same && i < length; i++) if (output[i] != current[i]) same = 0;
    if (same) return 0;
    dir = open(PRELOAD_PARENT, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (dir < 0) return 4;
    int fd = open(PRELOAD_PATH ".a7c-ui-new",
                  O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0644);
    if (fd < 0) { close(dir); return 4; }
    int ok = once_write_all(fd, output, (unsigned)length);
    if (fsync(fd)) ok = 0;
    if (close(fd)) ok = 0;
    /* Recheck current bytes immediately before replace; no concurrent config
     * editing is allowed during install/revoke. This is not a filesystem CAS. */
    long check_n = once_read_file(PRELOAD_PATH, before, sizeof(before));
    if (check_n != n) ok = 0;
    for (long i = 0; ok && i < n; i++) if (current[i] != before[i]) ok = 0;
    if (ok && rename(PRELOAD_PATH ".a7c-ui-new", PRELOAD_PATH)) ok = 0;
    if (ok && fsync(dir)) ok = 0;
    if (close(dir)) ok = 0;
    /* Preserve temp file on error for inspection; never overwrite it on retry. */
    return ok ? 0 : 4;
}

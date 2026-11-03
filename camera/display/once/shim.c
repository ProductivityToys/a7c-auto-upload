/* No constructor. Globally mapped shim, with behavior scoped to bootin -> im.
 * Failure to prepare/consume durably forwards the original exec unchanged. */
#include "protocol.h"
#include "platform.h"

static int claim(void) {
    char ticket[sizeof(TICKET_VALUE)];
    if (once_read_file(ONCE_ROOT "/armed", ticket, sizeof(ticket)) != sizeof(ticket) - 1)
        return 0;
    for (unsigned i = 0; i < sizeof(ticket) - 1; i++)
        if (ticket[i] != TICKET_VALUE[i]) return 0;
    /* O_EXCL is the cross-process winner. Never remove spent, even on failure. */
    int dir = open(ONCE_ROOT, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (dir < 0) return 0;
    int fd = open(ONCE_ROOT "/spent",
                  O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) { close(dir); return 0; }
    int ok = once_write_all(fd, TICKET_VALUE, sizeof(TICKET_VALUE) - 1);
    if (fsync(fd)) ok = 0;
    if (close(fd)) ok = 0;
    if (fsync(dir)) ok = 0;
    if (close(dir)) ok = 0;
    /* No injection unless both file and directory durability barriers succeed.
     * Directory fsync support on actual camera filesystem remains a preflight. */
    if (!ok) return 0;
    /* Revoke deletes armed. Recheck after fsync; committed exec can still race
     * a later revoke, so active-process cleanup always requires an exit. */
    if (once_read_file(ONCE_ROOT "/armed", ticket, sizeof(ticket)) != sizeof(ticket) - 1)
        return 0;
    for (unsigned i = 0; i < sizeof(ticket) - 1; i++)
        if (ticket[i] != TICKET_VALUE[i]) return 0;
    return 1;
}

EXPORT int execve(const char *path, char *const argv[], char *const env[]) {
    char exe[64];
    struct once_environment prepared;
    if (once_equal(path, "/usr/bin/im.elf")) {
        long n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
        if (n > 0 && n < (long)sizeof(exe) - 1) {
            exe[n] = 0;
            if (once_equal(exe, "/usr/bin/bootin.elf") &&
                once_prepare(env, &prepared) && claim())
                /* libc syscall converts kernel error return into errno. */
                return (int)syscall(11 /* ARM execve */, path, argv, prepared.pointers);
        }
    }
    return (int)syscall(11, path, argv, env);
}

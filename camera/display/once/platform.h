#ifndef A7C_UI_ONCE_PLATFORM_H
#define A7C_UI_ONCE_PLATFORM_H
#ifdef __arm__
extern int open(const char *, int, ...), close(int), fsync(int), unlink(const char *);
extern int rename(const char *, const char *), getpid(void);
extern long read(int, void *, unsigned long), write(int, const void *, unsigned long);
extern long readlink(const char *, char *, unsigned long), syscall(long, ...);
extern int *__errno_location(void);
#define errno (*__errno_location())
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 64
#define O_EXCL 128
#define O_NONBLOCK 2048
#define O_DIRECTORY 16384
#define O_NOFOLLOW 131072
#define O_CLOEXEC 524288
#define EINTR 4
#define ENOENT 2
#else
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#ifdef ONCE_TEST_SYSCALL
/* macOS syscall has a different signature; host tests never call it. */
extern long once_test_syscall(long, ...);
#define syscall once_test_syscall
#endif
#endif
/* Regular installed files only; nonblocking/nofollow reject accidental pipe/link use.
 * Reads one extra byte via caller's capacity to detect overlong files. */
static inline long once_read_file(const char *path, char *out, unsigned cap) {
    int fd = open(path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    unsigned used = 0, interrupted = 0;
    while (used < cap) {
        long n = read(fd, out + used, cap - used);
        if (n < 0 && errno == EINTR && interrupted++ < 3) continue;
        if (n < 0) { close(fd); return -1; }
        if (!n) break;
        used += (unsigned)n;
    }
    int rc = close(fd);
    return rc ? -1 : (long)used;
}
static inline int once_write_all(int fd, const char *data, unsigned n) {
    unsigned pos = 0, interrupted = 0;
    while (pos < n) {
        long w = write(fd, data + pos, n - pos);
        if (w < 0 && errno == EINTR && interrupted++ < 3) continue;
        if (w <= 0) return 0;
        pos += (unsigned)w;
    }
    return 1;
}
#endif

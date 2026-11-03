/* Host-only exec syscall substitute. Nothing is executed on the camera. */
#include "../once/protocol.h"
#include <assert.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>
extern int once_execve(const char *, char *const[], char *const[]);
static const char *caller;
static char **original_env, **original_argv;
static unsigned injected, restored, same_argv, syncs, fail_sync;
static const char *lookup(char *const env[], const char *name) {
    size_t n = strlen(name);
    for (unsigned i = 0; env[i]; i++)
        if (!strncmp(env[i], name, n) && env[i][n] == '=') return env[i] + n + 1;
    return 0;
}
long once_readlink(const char *path, char *out, unsigned long size) {
    assert(!strcmp(path, "/proc/self/exe"));
    size_t n = strlen(caller);
    assert(n < size); memcpy(out, caller, n);
    return (long)n;
}
int once_fsync(int fd) {
    if (++syncs == fail_sync) { errno = EIO; return -1; }
    return fsync(fd);
}
long once_test_syscall(long nr, ...) {
    assert(nr == 11);
    va_list args; va_start(args, nr);
    (void)va_arg(args, const char *);
    char **argv = va_arg(args, char **);
    char **env = va_arg(args, char **); va_end(args);
    same_argv = argv == original_argv;
    const char *load = lookup(env, "LD_PRELOAD");
    injected = env != original_env && load && !strncmp(load, LOAD_VALUE, strlen(LOAD_VALUE));
    if (injected) {
        assert(once_scrub(env) == 1);
        restored = 1;
        unsigned a = 0, b = 0;
        while (env[a]) a++;
        while (original_env[b]) b++;
        if (a != b) restored = 0;
        for (unsigned i = 0; i < b; i++) {
            unsigned matches = 0;
            for (unsigned j = 0; j < a; j++)
                if (!strcmp(original_env[i], env[j])) matches++;
            if (matches != 1) restored = 0;
        }
    } else restored = env == original_env;
    errno = EACCES; return -1;
}
int main(int argc, char **argv, char **env) {
    assert(argc == 4);
    caller = argv[1]; fail_sync = (unsigned)atoi(argv[3]);
    original_env = env; original_argv = argv;
    int rc = once_execve(argv[2], argv, env);
    assert(rc == -1 && errno == EACCES);
    printf("injected=%u restored=%u argv=%u errno=%d sync=%u\n",
           injected, restored, same_argv, errno, syncs);
    return 0;
}

/* Standalone diagnostic only. Never targets im, never changes preload files.
 * The alarm survives exec and bounds this direct child, not a kernel reset. */
#include "protocol.h"
#include "platform.h"
#ifndef CHECK_ROOT
#define CHECK_ROOT "/setting/a7c-debug/ram/ui-load-check"
#endif
#ifndef CHECK_TARGET
#define CHECK_TARGET "/bin/busybox"
#endif
#ifndef CHECK_SECONDS
#define CHECK_SECONDS 5
#endif
#ifdef __arm__
extern int fork(void), execve(const char *, char *const[], char *const[]);
extern int waitpid(int, int *, int), printf(const char *, ...), fflush(void *);
extern unsigned alarm(unsigned);
extern void _exit(int);
typedef void (*handler)(int);
extern handler signal(int, handler);
#else
#include <signal.h>
#include <sys/wait.h>
typedef void (*handler)(int);
#endif

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    char *load;
    if (once_equal(argv[1], "baseline")) load = 0;
    else if (once_equal(argv[1], "entry")) load = "LD_PRELOAD=" CHECK_ROOT "/entry.so";
    else if (once_equal(argv[1], "observer")) load = "LD_PRELOAD=" CHECK_ROOT "/observer.so";
    else if (once_equal(argv[1], "combined"))
        load = "LD_PRELOAD=" CHECK_ROOT "/entry.so:" CHECK_ROOT "/observer.so";
    else return 64;
    char *args[] = {CHECK_TARGET, "true", 0};
    char *env[] = {"PATH=/bin:/usr/bin", load, 0};
    printf("LOAD_CHECK_BEGIN mode=%s timeout=%u\n", argv[1], CHECK_SECONDS);
    fflush(0);
    int pid = fork();
    if (pid < 0) return 70;
    if (!pid) {
        if (signal(14, (handler)0) == (handler)-1) _exit(125);
        alarm(CHECK_SECONDS);
        execve(CHECK_TARGET, args, env);
        _exit(126);
    }
    printf("LOAD_CHECK_CHILD pid=%d\n", pid);
    fflush(0);
    int status = 0, result;
    do { result = waitpid(pid, &status, 0); } while (result < 0 && errno == EINTR);
    if (result != pid) return 71;
    int sig = status & 127, code = (status >> 8) & 255;
    printf("LOAD_CHECK_END signal=%d exit=%d\n", sig, code);
    fflush(0);
    return sig ? (sig == 14 ? 124 : 128 + sig) : code;
}

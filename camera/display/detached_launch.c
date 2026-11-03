/* Fixed, temporary double-fork launcher; no preload hooks or autostart. */
extern int fork(void), setsid(void), waitpid(int, int *, int), close(int);
extern int open(const char *, int, ...), dup2(int, int), chdir(const char *);
extern int execv(const char *, char *const []);
extern void _exit(int);
extern void (*signal(int, void (*)(int)))(int);
#ifndef COLLECTOR_LIMIT
#define COLLECTOR_LIMIT "180"
#endif
#ifndef COLLECTOR_PATH
#define COLLECTOR_PATH "/setting/a7c-debug/ram/ui-layout-once/collector.sh"
#endif

int main(void) {
    int child = fork(), status = 0;
    if (child < 0) return 111;
    if (child > 0) {
        if (waitpid(child, &status, 0) != child) return 112;
        return status == 0 ? 0 : 113;
    }
    signal(1, (void (*)(int))1); /* SIGHUP -> SIG_IGN */
    if (setsid() < 0) _exit(114);
    child = fork();
    if (child < 0) _exit(115);
    if (child > 0) _exit(0);
    if (chdir("/") != 0) _exit(116);
    for (int fd = 0; fd < 4096; ++fd) close(fd);
    if (open("/dev/null", 2) != 0) _exit(117);
    if (dup2(0, 1) != 1 || dup2(0, 2) != 2) _exit(118);
#ifdef COLLECTOR_UNTIMED
    /* Passive authenticated listener: waiting must not consume the user's
     * display window. The separate blink worker still has its own deadline. */
    char *const args[] = {"/bin/ash", COLLECTOR_PATH, (char *)0};
    execv("/bin/ash", args);
#else
    char *const args[] = {
        "busybox", "timeout", "-t", COLLECTOR_LIMIT, "-s", "TERM",
        "/bin/ash", COLLECTOR_PATH,
        (char *)0
    };
    execv("/bin/busybox", args);
#endif
    _exit(119);
}

/* Isolated ARM lab only. Fake bootin/im executables, never Sony programs. */
#include "../once/protocol.h"
#include "../once/platform.h"
extern int puts(const char *), fork(void), waitpid(int, int *, int);
extern int execve(const char *, char *const [], char *const []);
extern void _exit(int);
extern char *getenv(const char *);
struct entry_status { unsigned version, restored, is_im, pid; };
extern struct entry_status a7c_ui_once_entry_status __attribute__((weak));

static int put(const char *path, const char *bytes, unsigned length) {
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd < 0) return 0;
    int ok = once_write_all(fd, bytes, length);
    if (close(fd)) ok = 0;
    return ok;
}
static int present(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 0;
    close(fd);
    return 1;
}
static int child(const char *path, const char *mode) {
    int pid = fork(), status = 0;
    if (pid < 0) return 90;
    if (!pid) {
        char *args[] = {(char *)path, "child", (char *)mode, 0};
        /* The parent loaded shim, but this original target environment has none. */
        char *env[] = {"LD_LIBRARY_PATH=/lab", 0};
        execve(path, args, env);
        _exit(91);
    }
    if (waitpid(pid, &status, 0) != pid) return 92;
    return (status & 127) ? 93 : ((status >> 8) & 255);
}
int main(int argc, char **argv) {
    if (argc == 3 && once_equal(argv[1], "child")) {
        int loaded = &a7c_ui_once_entry_status != 0;
        int expected = once_equal(argv[2], "loaded");
        if (loaded != expected) return 10;
        if (getenv("LD_PRELOAD") || getenv("A7C_UI_ONCE") ||
            getenv("A7C_UI_SAVED_LD_PRELOAD")) return 11;
        if (loaded && (a7c_ui_once_entry_status.version != 1 ||
                       a7c_ui_once_entry_status.restored != 1 ||
                       a7c_ui_once_entry_status.is_im != 1 ||
                       a7c_ui_once_entry_status.pid != (unsigned)getpid())) return 12;
        return 0;
    }
    if (argc != 2 || &a7c_ui_once_entry_status) return 64;
    const char *mode = argv[1];
    int missing = once_equal(mode, "no-ticket");
    int invalid = once_equal(mode, "bad-ticket");
    int spent = once_equal(mode, "spent");
    int wrong_caller = once_equal(mode, "wrong-caller");
    int wrong_target = once_equal(mode, "wrong-target");
    int failure = once_equal(mode, "exec-failure");
    int positive = once_equal(mode, "once");
    if (!(missing || invalid || spent || wrong_caller || wrong_target || failure || positive))
        return 64;
    char exe[80];
    long n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n <= 0 || n >= (long)sizeof(exe) - 1) return 20;
    exe[n] = 0;
    if (!once_equal(exe, wrong_caller ? "/usr/bin/other.elf" : "/usr/bin/bootin.elf"))
        return 21;
    if (!missing && !put(ONCE_ROOT "/armed", invalid ? "bad\n" : TICKET_VALUE,
                         invalid ? 4 : sizeof(TICKET_VALUE) - 1)) return 22;
    if (spent && !put(ONCE_ROOT "/spent", TICKET_VALUE, sizeof(TICKET_VALUE) - 1)) return 23;
    int rc = child(wrong_target ? "/usr/bin/other.elf" : "/usr/bin/im.elf",
                   positive ? "loaded" : "absent");
    if (rc != (failure ? 91 : 0)) return rc ? rc : 24;
    if (present(ONCE_ROOT "/spent") != (positive || spent || failure)) return 25;
    if (positive && (rc = child("/usr/bin/im.elf", "absent"))) return rc;
    if (failure && child("/usr/bin/im.elf", "absent") != 91) return 26;
    puts("A7C_ARM_EXEC_OK");
    return 0;
}

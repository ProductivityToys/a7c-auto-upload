/* Runs before im main. No Sony imports, allocation, IO writes, worker or lease.
 * The observer remains disarmed; this experiment proves loading only. */
#include "protocol.h"
#include "platform.h"
extern char **environ;
struct once_entry_status { unsigned version, environment_restored, is_im, pid; };
EXPORT struct once_entry_status a7c_ui_once_entry_status;
__attribute__((constructor)) static void entry(void) {
    char path[64];
    /* Also scrub if accidentally launched elsewhere, limiting further inheritance. */
    a7c_ui_once_entry_status.version = 1;
    a7c_ui_once_entry_status.environment_restored = (unsigned)once_scrub(environ);
    a7c_ui_once_entry_status.pid = (unsigned)getpid();
    long n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (n > 0 && n < (long)sizeof(path) - 1) {
        path[n] = 0;
        a7c_ui_once_entry_status.is_im = once_equal(path, "/usr/bin/im.elf");
    }
}

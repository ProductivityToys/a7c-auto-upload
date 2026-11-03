#include <assert.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
extern char **environ;
extern struct { unsigned version, restored, im, pid; } a7c_ui_once_entry_status;
int main(void) {
    assert(a7c_ui_once_entry_status.version == 1);
    assert(a7c_ui_once_entry_status.restored == 1);
    /* Real host process isn't im. The scrub still contains accidental inheritance. */
    assert(a7c_ui_once_entry_status.im == 0);
    assert(a7c_ui_once_entry_status.pid == (unsigned)getpid());
    puts("entry_constructor_ok"); fflush(stdout);
    char *args[] = {"env", 0};
    execve("/usr/bin/env", args, environ);
    return 1;
}

/* ILCE-7C 2.00 native layout-list query for all registered physical layers.
 * Omit parameter 2: handler 0x3ee6f4 receives no parameter, starts at zero,
 * and loops only while index < wrapper->count (0x3ee720..0x3ee72e).
 * This is one native query, no user-supplied indices or display mutations.
 */
extern unsigned int alarm(unsigned int);
extern int execv(const char *, char *const []);
extern int printf(const char *, ...);
extern int fflush(void *);

int main(void) {
    char *const args[] = {
        "/usr/bin/testcmd.elf", "--sync", "0x0083014b",
        "5", "1", "1", "1", (char *)0
    };
    printf("A7C_UI_LAYOUT_ALL_V1 event=5 list=1 registered_layers client_deadline=8s\n");
    fflush((void *)0);
    alarm(8);
    execv(args[0], args);
    printf("A7C_UI_LAYOUT_EXEC_FAILED\n");
    return 127;
}

/* Fixed layout-list query for actual ILCE-7C 2.00.
 * Event 5, numeric parameter 1=1 (list), parameter 2=0 (physical index).
 * No layout switching, widget modification, arbitrary parameters or model query.
 * The alarm bounds the client only; it cannot cancel a queued UI event.
 */
extern unsigned int alarm(unsigned int);
extern int execv(const char *, char *const []);
extern int printf(const char *, ...);
extern int fflush(void *);

int main(void) {
    char *const args[] = {
        "/usr/bin/testcmd.elf", "--sync", "0x0083014b",
        "5", "1", "1", "1", "1", "2", "0", (char *)0
    };
    printf("A7C_UI_LAYOUT_V1 event=5 list=1 physical_index=0 client_deadline=8s\n");
    fflush((void *)0);
    alarm(8);
    execv(args[0], args);
    printf("A7C_UI_LAYOUT_EXEC_FAILED\n");
    return 127;
}

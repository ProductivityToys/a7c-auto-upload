/* Fixed widget-list query for the observed ILCE-7C 2.00 playback layout.
 * Event 5, numeric parameters 1=2, 2=group ID, 3=layout ID.
 * libtestcmd parses these uint32 values with strtoul(base=0).
 * Native handler only enumerates widgets, including its closed-layout fallback.
 * No object address, writable property, layout switch or arbitrary argument.
 */
extern unsigned int alarm(unsigned int);
extern int execv(const char *, char *const []);
extern int printf(const char *, ...);
extern int fflush(void *);

int main(void) {
    char *const args[] = {
        "/usr/bin/testcmd.elf", "--sync", "0x0083014b",
        "5", "1", "1", "2", "1", "2", "0x1a3db4a3",
        "1", "3", "0xd90a4744", (char *)0
    };
    printf("A7C_UI_WIDGETS_PLAYBACK_V1 event=5 list=2 group=0x1a3db4a3 layout=0xd90a4744 client_deadline=8s\n");
    fflush((void *)0);
    alarm(8);
    execv(args[0], args);
    printf("A7C_UI_WIDGETS_EXEC_FAILED\n");
    return 127;
}

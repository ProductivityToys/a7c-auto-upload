/*
 * ILCE-7C 2.00 only. Request the native layout-test HELP branch.
 *
 * testcmd.elf encodes four numeric tokens:
 *   Event 5; parameter type 1 (number), parameter ID 1, value 0 (help).
 * The native UI thread handles the event. No widget mutation is requested.
 *
 * alarm survives exec. It bounds this client, NOT an already queued native
 * event; timeout must stop the experiment, not trigger repeated submissions.
 * Successful transport/exit does not prove UI processing. Collect the native
 * help log separately. No model-query event is sent (those can wait forever
 * inside the native callback).
 */
extern unsigned int alarm(unsigned int);
extern int execv(const char *, char *const []);
extern int printf(const char *, ...);
extern int fflush(void *);

int main(void)
{
    char *const args[] = {
        "/usr/bin/testcmd.elf", "--sync", "0x0083014b",
        "5", "1", "1", "0", (char *)0
    };
    printf("A7C_UI_HELP_V1 event=5 param=1 value=0 client_deadline=8s\n");
    fflush((void *)0);
    alarm(8);
    execv(args[0], args);
    printf("A7C_UI_HELP_EXEC_FAILED\n");
    return 127;
}

/* Runs only in the isolated loader lab; no camera, Sony library or UI calls. */
extern int puts(const char *);
extern char *getenv(const char *);
struct entry_status { unsigned version, restored, is_im, pid; };
extern struct entry_status a7c_ui_once_entry_status __attribute__((weak));
static int equal(const char *a, const char *b) {
    if (!a || !b) return a == b;
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}
int main(int argc, char **argv) {
    if (argc != 2) return 64;
    int present = &a7c_ui_once_entry_status != 0;
    if (equal(argv[1], "absent")) {
        if (present) return 1;
    } else {
        if (!present || a7c_ui_once_entry_status.version != 1 ||
            !a7c_ui_once_entry_status.pid || a7c_ui_once_entry_status.is_im) return 2;
        if (equal(argv[1], "unmarked")) {
            if (a7c_ui_once_entry_status.restored) return 3;
        } else if (equal(argv[1], "unset") || equal(argv[1], "saved") ||
                   equal(argv[1], "empty")) {
            if (!a7c_ui_once_entry_status.restored ||
                getenv("A7C_UI_ONCE") || getenv("A7C_UI_SAVED_LD_PRELOAD")) return 4;
            const char *expected = equal(argv[1], "unset") ? (const char *)0 :
                (equal(argv[1], "empty") ? "" : "/lab/libc.so.6");
            if (!equal(getenv("LD_PRELOAD"), expected)) return 5;
        } else return 64;
    }
    puts("A7C_ARM_ENTRY_OK");
    return 0;
}

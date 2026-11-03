#ifndef A7C_UI_ONCE_H
#define A7C_UI_ONCE_H
/* Fixed, root-owned experiment directory; installer refuses reuse. */
#ifndef ONCE_ROOT
#define ONCE_ROOT "/setting/a7c-display-once"
#endif
#define SHIM_PATH ONCE_ROOT "/exec-shim.so"
#define ENTRY_PATH ONCE_ROOT "/entry.so"
#define OBSERVER_PATH ONCE_ROOT "/observer.so"
#define LOAD_VALUE ENTRY_PATH ":" OBSERVER_PATH
#define TICKET_VALUE "a7c-ui-once-v1\n"
#define ENV_MARK "A7C_UI_ONCE=v1"
#define SAVED_PREFIX "A7C_UI_SAVED_"
#define SAVED_NAME SAVED_PREFIX "LD_PRELOAD="
#define ENV_LIMIT 128
#define VALUE_LIMIT 2048
#define EXPORT __attribute__((visibility("default")))
struct once_environment {
    char *pointers[ENV_LIMIT + 4];
    char preload[VALUE_LIMIT];
    char saved[VALUE_LIMIT];
};
unsigned once_length(const char *s, unsigned limit);
int once_equal(const char *a, const char *b);
int once_prefix(const char *s, const char *prefix);
/* No allocation, process or file access. Failure leaves caller env untouched. */
int once_prepare(char *const env[], struct once_environment *out);
/* In-place array compaction; restore exact prior value, including unset/empty.
 * Returns 1 only for the exact environment created by once_prepare. */
int once_scrub(char **env);
/* Strip one exact owned line. Exact installation match restores original bytes.
 * Otherwise preserve unrelated current bytes. -1 means ambiguous, no write. */
int once_remove_line(const char *current, unsigned n,
                     const char *before, unsigned before_n, char *out);
#endif

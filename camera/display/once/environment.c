#include "protocol.h"
unsigned once_length(const char *s, unsigned limit) {
    unsigned n = 0;
    if (!s) return limit;
    while (n < limit && s[n]) n++;
    return n;
}
int once_equal(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}
int once_prefix(const char *s, const char *prefix) {
    if (!s) return 0;
    while (*prefix) if (*s++ != *prefix++) return 0;
    return 1;
}
static unsigned copy(char *dst, unsigned n, const char *s) {
    while (*s) dst[n++] = *s++;
    dst[n] = 0;
    return n;
}
int once_prepare(char *const env[], struct once_environment *out) {
    unsigned count = 0, idx = 0, old_count = 0;
    const char *old = 0;
    if (!env || !out) return 0;
    while (count < ENV_LIMIT && env[count]) {
        const char *s = env[count++];
        if (once_prefix(s, "A7C_UI_ONCE=") || once_prefix(s, SAVED_NAME)) return 0;
        if (once_prefix(s, "LD_PRELOAD=")) { old = s + 11; old_count++; }
    }
    if (count == ENV_LIMIT || old_count > 1) return 0;
    if (old && once_length(old, VALUE_LIMIT) >=
        VALUE_LIMIT - sizeof("LD_PRELOAD=" LOAD_VALUE ":") - sizeof(SAVED_NAME))
        return 0;
    /* Refuse pre-existing observer injection, even under a valid earlier ticket. */
    if (old) {
        for (unsigned i = 0; old[i]; i++)
            if (once_prefix(old + i, ENTRY_PATH) || once_prefix(old + i, OBSERVER_PATH))
                return 0;
    }
    for (unsigned i = 0; i < count; i++)
        if (!once_prefix(env[i], "LD_PRELOAD=")) out->pointers[idx++] = env[i];
    unsigned n = copy(out->preload, 0, "LD_PRELOAD=" LOAD_VALUE);
    if (old) { n = copy(out->preload, n, ":"); copy(out->preload, n, old); }
    out->pointers[idx++] = out->preload;
    if (old) {
        n = copy(out->saved, 0, SAVED_NAME); copy(out->saved, n, old);
        out->pointers[idx++] = out->saved;
    }
    out->pointers[idx++] = (char *)ENV_MARK;
    out->pointers[idx] = 0;
    return 1;
}
int once_scrub(char **env) {
    unsigned n = 0, marks = 0, loads = 0, saves = 0, j = 0;
    char *load = 0, *saved = 0;
    if (!env) return 0;
    while (n < ENV_LIMIT + 3 && env[n]) {
        char *s = env[n++];
        if (once_prefix(s, "A7C_UI_ONCE=")) {
            if (!once_equal(s, ENV_MARK)) return 0;
            marks++;
        }
        if (once_prefix(s, "LD_PRELOAD=")) { load = s + 11; loads++; }
        if (once_prefix(s, SAVED_NAME)) {
            saved = s + sizeof(SAVED_NAME) - 1; saves++;
        }
    }
    if (n == ENV_LIMIT + 3 || marks != 1 || loads != 1 || saves > 1) return 0;
    if (saved) {
        if (!once_prefix(load, LOAD_VALUE ":") ||
            !once_equal(load + sizeof(LOAD_VALUE ":" ) - 1, saved)) return 0;
    } else if (!once_equal(load, LOAD_VALUE)) return 0;
    for (unsigned i = 0; i < n; i++) {
        char *s = env[i];
        if (once_prefix(s, "LD_PRELOAD=") || once_prefix(s, "A7C_UI_ONCE=")) continue;
        if (once_prefix(s, SAVED_NAME)) s += sizeof(SAVED_PREFIX) - 1;
        env[j++] = s;
    }
    env[j] = 0;
    return 1;
}
static int bytes_equal(const char *a, const char *b, unsigned n) {
    for (unsigned i = 0; i < n; i++) if (a[i] != b[i]) return 0;
    return 1;
}
int once_remove_line(const char *cur, unsigned n,
                     const char *before, unsigned bn, char *out) {
    const char owned[] = SHIM_PATH;
    unsigned len = sizeof(owned) - 1, found = 0, j = 0;
    for (unsigned i = 0; i < n; i++) if (!cur[i]) return -1;
    for (unsigned i = 0; i < bn; i++) if (!before[i]) return -1;
    unsigned sep = bn && before[bn - 1] != '\n';
    if (before && n == bn + sep + len + 1 && bytes_equal(cur, before, bn) &&
        (!sep || cur[bn] == '\n') && bytes_equal(cur + bn + sep, owned, len) &&
        cur[n - 1] == '\n') {
        for (unsigned i = 0; i < bn; i++) out[i] = before[i];
        return (int)bn;
    }
    for (unsigned i = 0; i < n;) {
        unsigned start = i;
        while (i < n && cur[i] != '\n') {
            if (!cur[i]) return -1;
            i++;
        }
        unsigned end = i;
        if (i < n) i++;
        if (end - start == len && bytes_equal(cur + start, owned, len)) {
            if (++found > 1) return -1;
            continue;
        }
        /* A combined/whitespace-altered owned entry requires manual review. */
        for (unsigned k = start; k + len <= end; k++)
            if (bytes_equal(cur + k, owned, len)) return -1;
        for (unsigned k = start; k < i; k++) out[j++] = cur[k];
    }
    return (int)j;
}

/* Exact ILCE-7C 2.00 only. The intercepted original is an audited no-op.
 * No constructor, UI mutation, allocation, worker, file/network write or lease.
 * Loading/rebinding and runtime hash verification are NOT implemented here. */
#include "passive.h"

struct ui_timespec { long sec, nsec; };
extern int getpid(void);
extern long syscall(long, ...);
extern long readlink(const char *, char *, unsigned long);
static unsigned lock;
static struct ui_observation record;
static struct ui_native_api native;
static struct ui_timespec deadline;
static int enter(void) { return !__atomic_exchange_n(&lock, 1, __ATOMIC_ACQUIRE); }
static void leave(void) { __atomic_store_n(&lock, 0, __ATOMIC_RELEASE); }

static int now(struct ui_timespec *t) {
    /* Audited 2.00 librt uses ARM EABI 263 for CLOCK_MONOTONIC.
     * Avoid adding librt's libpthread dependency at early preload time. */
    return syscall(263, 1 /* Linux CLOCK_MONOTONIC */, t) == 0 &&
        t->sec >= 0 && t->nsec >= 0 && t->nsec < 1000000000;
}
static int current_context(struct ui_timespec *t) {
    if (!now(t) || (ui_u32)getpid() != record.pid) {
        record.state = UI_FAILED;
        return 0;
    }
    if (t->sec > deadline.sec ||
        (t->sec == deadline.sec && t->nsec >= deadline.nsec)) {
        record.state = UI_EXPIRED;
        return 0;
    }
    return 1;
}
static int is_im(void) {
    static const char expected[] = "/usr/bin/im.elf";
    char path[64];
    long n = readlink("/proc/self/exe", path, sizeof(path));
    if (n != (long)sizeof(expected) - 1) return 0;
    for (long i = 0; i < n; i++) if (path[i] != expected[i]) return 0;
    return 1;
}
int a7c_ui_observer_arm(const struct ui_native_api *api,
                        ui_addr vtable, ui_u32 runtime_id,
                        ui_u32 nonce, ui_u32 ttl) {
    struct ui_timespec t;
    int rc = -1;
    if (!enter()) return -2;
    /* Scalar assignments avoid a freestanding compiler-generated memset. */
    record.version = 2; record.state = UI_IDLE;
    native.param_get = 0; native.widget_id = 0; native.id_value = 0;
    record.pid = record.tid = record.runtime_id = record.nonce = 0;
    record.object = record.vtable = 0;
    record.monotonic_seconds = record.monotonic_nanoseconds = 0;
    if (!api || api->version != 2 || api->bytes != sizeof(*api) ||
        !api->param_get || !api->widget_id || !api->id_value ||
        !vtable || (vtable & 3) || !runtime_id || !nonce || !ttl || ttl > 60)
        goto done;
    rc = -3;
    if (!is_im() || !now(&t) || t.sec > __LONG_MAX__ - (long)ttl)
        goto done;
    int pid = getpid();
    if (pid <= 0) goto done;
    native = *api;
    record.pid = (ui_u32)pid;
    record.vtable = vtable; record.runtime_id = runtime_id; record.nonce = nonce;
    deadline.sec = t.sec + ttl; deadline.nsec = t.nsec;
    record.state = UI_ARMED;
    rc = 0;
done:
    leave();
    return rc;
}
int a7c_ui_observer_disarm(void) {
    if (!enter()) return -2;
    if (record.state == UI_ARMED) record.state = UI_IDLE;
    leave();
    return 0;
}
int a7c_ui_observer_snapshot(struct ui_observation *out) {
    struct ui_timespec t;
    if (!out) return -1;
    if (!enter()) return -2;
    if (record.state == UI_ARMED) (void)current_context(&t);
    *out = record;
    leave();
    return 0;
}
static int number_is(const void *params, unsigned long key, ui_u32 expected) {
    const unsigned char *p = native.param_get(params, key, 1 /* PrmNumber */);
    /* Audited numeric payload at +0x10; no generic ParamList struct casting. */
    return p && *(const ui_u32 *)(p + 0x10) == expected;
}
void ui_custom_test(void *widget, const void *params) {
    struct ui_timespec t;
    if (!enter()) return; /* Never wait/spin on the UI thread, including reentry. */
    if (record.state != UI_ARMED || !current_context(&t) || !widget || !params)
        goto done;
    if (*(const ui_addr *)widget != record.vtable) goto done;
    if (!number_is(params, 1, 0x1a3db4a3) ||
        !number_is(params, 2, 0xd90a4744) ||
        !number_is(params, 3, 0x53034e72) ||
        !number_is(params, 4, record.nonce)) goto done;
    const void *id = native.widget_id(widget);
    if (!id || native.id_value(id) != record.runtime_id) goto done;
    long tid = syscall(224 /* ARM EABI __NR_gettid */);
    if (tid <= 0 || (unsigned long)tid > 0xffffffffUL) {
        record.state = UI_FAILED;
        goto done;
    }
    record.tid = (ui_u32)tid; record.object = (ui_addr)widget;
    record.monotonic_seconds = t.sec; record.monotonic_nanoseconds = t.nsec;
    record.state = UI_CAPTURED; /* One matching object; child calls become no-ops. */
done:
    leave();
}

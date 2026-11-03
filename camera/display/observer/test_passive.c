/* Host-only native ABI/platform stand-ins; never linked into camera artifact. */
#include "passive.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>

struct ui_timespec { long sec, nsec; };
struct fake_widget { ui_addr vtable; ui_u32 id; };
struct fake_number { ui_u32 padding[4], value; };
struct fake_params { struct fake_number n[4]; unsigned present, number_types; };
const void *fake_param_get(const void *, unsigned long, unsigned long);
const void *fake_widget_id(const void *);
ui_u32 fake_id_value(const void *);
static const struct ui_native_api native = {
    2, sizeof(struct ui_native_api), fake_param_get, fake_widget_id, fake_id_value
};
static long seconds = 100, nanos = 500, fake_tid = 42;
static int fake_pid = 20, clock_error, wrong_process, recurse;
static unsigned reads, calls, cases;
static const ui_addr expected_vtable = 0x1000;
static struct fake_widget target = {0x1000, 46132};
static struct fake_params request = {
    {{{0}, 0x1a3db4a3}, {{0}, 0xd90a4744}, {{0}, 0x53034e72}, {{0}, 0x12345678}},
    15, 15
};
int fake_clock_gettime(int which, struct ui_timespec *out) {
    assert(which == 1);
    calls++;
    out->sec = seconds; out->nsec = nanos;
    return clock_error ? -1 : 0;
}
int fake_getpid(void) { calls++; return fake_pid; }
long fake_syscall(long number, ...) {
    if (number == 263) {
        va_list args;
        va_start(args, number);
        int which = va_arg(args, int);
        struct ui_timespec *out = va_arg(args, struct ui_timespec *);
        va_end(args);
        return fake_clock_gettime(which, out);
    }
    assert(number == 224); calls++; return fake_tid;
}
long fake_readlink(const char *path, char *out, unsigned long cap) {
    const char *exe = wrong_process ? "/usr/bin/other" : "/usr/bin/im.elf";
    assert(!strcmp(path, "/proc/self/exe"));
    assert(cap > strlen(exe));
    memcpy(out, exe, strlen(exe));
    return (long)strlen(exe);
}
const void *fake_param_get(const void *p, unsigned long key, unsigned long type) {
    const struct fake_params *params = p;
    assert(key >= 1 && key <= 4 && type == 1);
    reads++;
    if (recurse) {
        struct ui_observation out;
        recurse = 0;
        /* All paths must reject contention immediately, never spin/deadlock. */
        assert(a7c_ui_observer_snapshot(&out) == -2);
        assert(a7c_ui_observer_disarm() == -2);
        assert(a7c_ui_observer_arm(&native, expected_vtable, target.id, 1, 5) == -2);
        ui_custom_test(&target, &request);
    }
    unsigned bit = 1u << (key - 1);
    return (params->present & bit) && (params->number_types & bit)
        ? &params->n[key - 1] : 0;
}
const void *fake_widget_id(const void *p) {
    reads++;
    return &((const struct fake_widget *)p)->id;
}
ui_u32 fake_id_value(const void *p) { reads++; return *(const ui_u32 *)p; }
static void arm(void) {
    assert(a7c_ui_observer_arm(&native, expected_vtable, target.id, 0x12345678, 10) == 0);
}
static struct ui_observation snapshot(unsigned state) {
    struct ui_observation out;
    assert(a7c_ui_observer_snapshot(&out) == 0);
    assert(out.state == state);
    return out;
}
static void pass(const char *name) { cases++; printf("PASS %s\n", name); }

int main(void) {
    ui_custom_test((void *)1, (void *)1);
    assert(reads == 0 && calls == 0);
    pass("inert before explicit arm; no input dereference or system calls");

    wrong_process = 1;
    assert(a7c_ui_observer_arm(&native, expected_vtable, target.id, 1, 10) == -3);
    wrong_process = 0; snapshot(UI_IDLE);
    pass("wrong executable cannot arm");

    assert(a7c_ui_observer_arm(0, expected_vtable, target.id, 1, 10) == -1);
    for (unsigned k = 0; k < 5; k++) {
        struct ui_native_api bad = native;
        if (k == 0) bad.version = 1;
        if (k == 1) bad.bytes--;
        if (k == 2) bad.param_get = 0;
        if (k == 3) bad.widget_id = 0;
        if (k == 4) bad.id_value = 0;
        assert(a7c_ui_observer_arm(&bad, expected_vtable, target.id, 1, 10) == -1);
    }
    pass("native API is mandatory, versioned, sized and complete");

    assert(a7c_ui_observer_arm(&native, 0, target.id, 1, 10) == -1);
    assert(a7c_ui_observer_arm(&native, 0x1001, target.id, 1, 10) == -1);
    assert(a7c_ui_observer_arm(&native, expected_vtable, 0, 1, 10) == -1);
    assert(a7c_ui_observer_arm(&native, expected_vtable, target.id, 0, 10) == -1);
    assert(a7c_ui_observer_arm(&native, expected_vtable, target.id, 1, 0) == -1);
    assert(a7c_ui_observer_arm(&native, expected_vtable, target.id, 1, 61) == -1);
    assert(a7c_ui_observer_snapshot(0) == -1);
    pass("invalid arm arguments and null output");

    arm(); ui_custom_test(0, &request); ui_custom_test(&target, 0);
    struct fake_widget other = {0x2000, target.id};
    ui_custom_test(&other, (void *)1); snapshot(UI_ARMED);
    pass("null input and wrong vtable rejected before parameter reads");

    for (unsigned k = 0; k < 4; k++) {
        struct fake_params bad = request;
        bad.present &= ~(1u << k);
        ui_custom_test(&target, &bad); snapshot(UI_ARMED);
        bad = request; bad.number_types &= ~(1u << k);
        ui_custom_test(&target, &bad); snapshot(UI_ARMED);
        bad = request; bad.n[k].value ^= 1;
        ui_custom_test(&target, &bad); snapshot(UI_ARMED);
    }
    pass("all four parameters require exact integer type and value");

    other.vtable = expected_vtable; other.id++;
    ui_custom_test(&other, &request); snapshot(UI_ARMED);
    pass("child or stale runtime ID cannot consume sample");

    recurse = 1;
    ui_custom_test(&target, &request);
    struct ui_observation sample = snapshot(UI_CAPTURED);
    assert(sample.version == 2 && sample.pid == 20 && sample.tid == 42);
    assert(sample.runtime_id == target.id && sample.nonce == 0x12345678);
    assert(sample.object == (ui_addr)&target && sample.vtable == expected_vtable);
    assert(sample.monotonic_seconds == 100 && sample.monotonic_nanoseconds == 500);
    pass("matching callback records scalar evidence; reentry does not block");

    unsigned old_reads = reads, old_calls = calls;
    ui_custom_test((void *)1, (void *)1);
    assert(reads == old_reads && calls == old_calls);
    snapshot(UI_CAPTURED);
    pass("duplicate and subsequent child callbacks are inert");

    arm(); seconds = 110; nanos = 499; snapshot(UI_ARMED);
    nanos = 500; ui_custom_test((void *)1, (void *)1); snapshot(UI_EXPIRED);
    pass("deadline boundary cancels before touching native object");

    seconds = 200; arm(); seconds += 10; snapshot(UI_EXPIRED);
    pass("snapshot also expires arm without needing a callback");

    arm(); clock_error = 1;
    ui_custom_test((void *)1, (void *)1); snapshot(UI_FAILED);
    assert(a7c_ui_observer_arm(&native, expected_vtable, target.id, 1, 10) == -3);
    clock_error = 0;
    pass("clock failure cancels and prevents arming");

    arm(); fake_pid++;
    ui_custom_test((void *)1, (void *)1); snapshot(UI_FAILED);
    fake_pid--;
    pass("fork or process identity change cancels");

    arm(); fake_tid = -1;
    ui_custom_test(&target, &request); snapshot(UI_FAILED);
    fake_tid = 42;
    pass("failed thread lookup produces no captured sample");

    arm(); assert(a7c_ui_observer_disarm() == 0);
    ui_custom_test((void *)1, (void *)1); snapshot(UI_IDLE);
    arm(); assert(a7c_ui_observer_arm(&native, 0, 0, 0, 0) == -1);
    ui_custom_test((void *)1, (void *)1); snapshot(UI_IDLE);
    pass("explicit cancel and invalid rearm revoke previous activation");

    struct ui_native_api temporary = native;
    assert(a7c_ui_observer_arm(&temporary, expected_vtable, target.id, 0x12345678, 10) == 0);
    temporary.param_get = 0; temporary.widget_id = 0; temporary.id_value = 0;
    ui_custom_test(&target, &request); snapshot(UI_CAPTURED);
    pass("API table is copied and does not retain caller stack storage");
    printf("%u boundary groups passed\n", cases);
    return 0;
}

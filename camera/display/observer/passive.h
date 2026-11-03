/* Research ABI v2. Internal, same-process calls only; not a network API. */
#ifndef A7C_UI_PASSIVE_H
#define A7C_UI_PASSIVE_H
typedef __UINT32_TYPE__ ui_u32;
typedef __UINTPTR_TYPE__ ui_addr;
#define UI_EXPORT __attribute__((visibility("default")))
enum ui_state { UI_IDLE, UI_ARMED, UI_CAPTURED, UI_EXPIRED, UI_FAILED };
struct ui_native_api {
    ui_u32 version, bytes;
    const void *(*param_get)(const void *, unsigned long, unsigned long);
    const void *(*widget_id)(const void *);
    ui_u32 (*id_value)(const void *);
};
struct ui_observation {
    ui_u32 version, state, pid, tid, runtime_id, nonce;
    ui_addr object, vtable;
    long monotonic_seconds, monotonic_nanoseconds;
};
/* Caller must first verify mapped firmware hashes, each native API address,
 * symbol binding, vtable relocation and a fresh runtime ID. No historical IDs
 * are defaults. The API table is copied; caller must keep its code mapped until
 * disarm succeeds. No dlopen/dlsym or native-library imports occur here.
 * ttl is 1..60 seconds. Returns 0, -1 invalid, -2 busy, -3 context/clock error.
 * A failed arm leaves any previous arm cancelled. Busy never changes state. */
UI_EXPORT int a7c_ui_observer_arm(const struct ui_native_api *api,
                                 ui_addr vtable, ui_u32 runtime_id,
                                 ui_u32 nonce, ui_u32 ttl);
UI_EXPORT int a7c_ui_observer_disarm(void);
/* Copies scalar evidence only. Never dereference a recorded object later.
 * Expiry is evaluated at callback/snapshot time; there is no timer thread. */
UI_EXPORT int a7c_ui_observer_snapshot(struct ui_observation *out);
UI_EXPORT void ui_custom_test(void *widget, const void *params)
    __asm__("_ZN13AppWidgetBase20widgetUserTestCustomEPK9ParamList");
#endif

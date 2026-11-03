/* Marker-only module: no constructors, imports, threads, files or graphics.
 * Native module manager invokes these six callbacks. State is owned by this
 * DSO and inspected by a separate process; no pointer is installed elsewhere. */
typedef unsigned U;
struct marker_state { U magic,version,init,exit,suspend,resume,inactive,active; };
__attribute__((visibility("default"))) volatile struct marker_state a7c_native_marker =
    {0x41374d31U,1,0,0,0,0,0,0};
#define API __attribute__((visibility("default")))
API int IM_SAMPLE_SO_init(void) { a7c_native_marker.init++;return 0; }
API int IM_SAMPLE_SO_exit(void) { a7c_native_marker.exit++;return 0; }
API int IM_SAMPLE_SO_sus(void) { a7c_native_marker.suspend++;return 0; }
API int IM_SAMPLE_SO_res(void) { a7c_native_marker.resume++;return 0; }
API int IM_SAMPLE_SO_inact(void) { a7c_native_marker.inactive++;return 0; }
API int IM_SAMPLE_SO_act(void) { a7c_native_marker.active++;return 0; }

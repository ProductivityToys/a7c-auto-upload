/* Offline-buildable single-frame module. No live probe/installer is provided.
 * The controller must own the short display window and current-page checks;
 * never wait inside an im callback. Existing production DDS must be inactive.
 */
#include "native_progress_frame.h"
#define API __attribute__((visibility("default")))
API struct {
    U magic,version,init,exit,suspend,resume,inactive,active;
    int show_rc,clear_rc;
    struct progress_frame_result show,clear;
} a7c_native_marker={.magic=0x41374d31,
#ifdef A7C_FRAME_EXTERNAL_REDRAW
    .version=9
#else
    .version=7
#endif
};
API int IM_SAMPLE_SO_init(void) {
    if(a7c_native_marker.init++)return -1;
    return a7c_native_marker.show_rc=native_progress_frame(
        (U)&TextRM_loadFont-0x57d271,42,&a7c_native_marker.show);
}
API int IM_SAMPLE_SO_exit(void) {
    if(a7c_native_marker.exit++)return a7c_native_marker.clear_rc;
#ifndef A7C_FRAME_EXTERNAL_REDRAW
    /* A failed submit may still have touched the destination. */
    if(a7c_native_marker.show.submit_attempted)
        a7c_native_marker.clear_rc=native_progress_frame(
            (U)&TextRM_loadFont-0x57d271,-1,&a7c_native_marker.clear);
#endif
    return a7c_native_marker.clear_rc;
}
API int IM_SAMPLE_SO_sus(void){a7c_native_marker.suspend++;return 0;}
API int IM_SAMPLE_SO_res(void){a7c_native_marker.resume++;return 0;}
API int IM_SAMPLE_SO_inact(void){a7c_native_marker.inactive++;return 0;}
API int IM_SAMPLE_SO_act(void){a7c_native_marker.active++;return 0;}

/* ILCE-7C 2.00, one-shot event forwarding/TID observation, no graphics.
 * Controller pins the running firmware and retains this DSO mapping/file.
 * Native unload is not proof of dlclose; never overwrite this mapped file. */
#include "event_handoff.h"
#include "event_state.h"
typedef unsigned U;
extern int syscall(int,...);
extern int TextRM_loadFont(const char *,U *); /* address anchor, never called */
#define API __attribute__((visibility("default")))
API struct event_marker a7c_native_marker={.magic=0x41374d31,.version=10,
    .prepare_rc=-999,.restore_rc=-999,.capture_rc=-999};
static struct event_handoff handoff;
static void capture(void) {
    U ts[2]={0,0};int tid=syscall(224),rc=syscall(263,1,ts);
    a7c_native_marker.tid=tid>0?(U)tid:0;
    a7c_native_marker.sec=ts[0];a7c_native_marker.nsec=ts[1];
    a7c_native_marker.capture_rc=tid>0&&!rc&&ts[1]<1000000000U?0:-1;
    __atomic_store_n(&a7c_native_marker.captured,1,__ATOMIC_RELEASE);
}
static void event_entry(void *event){event_handoff_enter(&handoff,event);}
API int IM_SAMPLE_SO_init(void) {
    if(a7c_native_marker.init++)return -1;
    U base=(U)&TextRM_loadFont-0x57d271;
    const unsigned char expected[16]={0xb0,0xb5,0,0xaf,4,0x46,0x18,0xf5,
                                     0x8c,0xec,0x0d,0x4b,0x98,0x42,0x15,0xd1};
    int rc=-2;
    if(base<0x1000000U||base>0x70000000U||(base&4095))goto done;
    for(U i=0;i<16;i++)if(*(const unsigned char *)(base+0x3ef544+i)!=expected[i])goto done;
    U view=*(U *)(base+0x1488fdc);
    if(view<0x8000U||view>=0x80000000U||(view&3))goto done;
    U internal=*(U *)(view+0x14);
    if(internal<0x8000U||internal>=0x80000000U||(internal&3))goto done;
    a7c_native_marker.view=view;a7c_native_marker.internal=internal;
    a7c_native_marker.slot=internal+0x14;
    a7c_native_marker.original=base+0x3ef545;
    int tid=syscall(224);if(tid<=0)goto done;
    a7c_native_marker.init_tid=(U)tid;
    rc=event_handoff_prepare(&handoff,(void *)(internal+0x14),
                            (void *)(base+0x3ef545),event_entry,capture);
done:
    a7c_native_marker.prepare_rc=rc;return rc;
}
API int IM_SAMPLE_SO_exit(void) {
    if(a7c_native_marker.exit++)return a7c_native_marker.restore_rc;
    int tid=syscall(224);a7c_native_marker.exit_tid=tid>0?(U)tid:0;
    return a7c_native_marker.restore_rc=handoff.initialized?event_handoff_restore(&handoff):0;
}
API int IM_SAMPLE_SO_sus(void){a7c_native_marker.suspend++;return 0;}
API int IM_SAMPLE_SO_res(void){a7c_native_marker.resume++;return 0;}
API int IM_SAMPLE_SO_inact(void){a7c_native_marker.inactive++;return 0;}
API int IM_SAMPLE_SO_act(void){a7c_native_marker.active++;return 0;}

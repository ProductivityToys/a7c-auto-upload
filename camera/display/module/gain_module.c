/* ILCE-7C 2.00 one-shot GraphicsSystem gain-thread observation.
 * No drawing/resources; always forward original gain. Retain immutable DSO.
 * event_marker ABI reused: view/internal both hold the fixed callback table. */
#include "frame_handoff.h"
#include "event_state.h"
typedef unsigned U;
extern int syscall(int,...);
extern int TextRM_loadFont(const char *,U *); /* address anchor only */
#define API __attribute__((visibility("default")))
#ifdef GAIN_SCOPE_TRIAL
#include "gain_scope.h"
API struct { struct event_marker event; struct gain_scope scope; } a7c_native_marker={
    .event={.magic=0x41374d31,.version=15,.prepare_rc=-999,.restore_rc=-999,.capture_rc=-999},
    .scope={.rc=-999}};
#define MARKER a7c_native_marker.event
#else
API struct event_marker a7c_native_marker={.magic=0x41374d31,.version=11,
    .prepare_rc=-999,.restore_rc=-999,.capture_rc=-999};
#define MARKER a7c_native_marker
#endif
static struct frame_handoff handoff;
static void capture(void) {
    U ts[2]={0,0};int tid=syscall(224),rc=syscall(263,1,ts);
    MARKER.tid=tid>0?(U)tid:0;
    MARKER.sec=ts[0];MARKER.nsec=ts[1];
    MARKER.capture_rc=tid>0&&!rc&&ts[1]<1000000000U?0:-1;
#ifdef GAIN_SCOPE_TRIAL
    int scope_rc=gain_scope_read((U)&TextRM_loadFont-0x57d271,&a7c_native_marker.scope);
    if(scope_rc)MARKER.capture_rc=scope_rc;
#endif
    __atomic_store_n(&MARKER.captured,1,__ATOMIC_RELEASE);
}
static void gain_entry(void){frame_handoff_enter(&handoff);}
API int IM_SAMPLE_SO_init(void) {
    if(MARKER.init++)return -1;
    U base=(U)&TextRM_loadFont-0x57d271;
    const unsigned char expected[16]={0x43,0x4b,0x90,0xb5,0x85,0xb0,0x7b,0x44,
                                      0x02,0xaf,0x1b,0x78,0x64,0x2b,0x04,0xd1};
    int rc=-2;
    if(base<0x1000000U||base>0x70000000U||(base&4095))goto done;
    for(U i=0;i<16;i++)if(*(const unsigned char *)(base+0x675278+i)!=expected[i])goto done;
    U table=*(U *)(base+0x1453914);
    if(table!=base+0x14539d8)goto done;
    MARKER.view=table;MARKER.internal=table;
    MARKER.slot=table+0x5c;
    MARKER.original=base+0x675279;
    int tid=syscall(224);if(tid<=0)goto done;
    MARKER.init_tid=(U)tid;
    rc=frame_handoff_prepare(&handoff,(void *)(table+0x5c),
                            (void *)(base+0x675279),gain_entry,capture);
done:
    MARKER.prepare_rc=rc;return rc;
}
API int IM_SAMPLE_SO_exit(void) {
    if(MARKER.exit++)return MARKER.restore_rc;
    int tid=syscall(224);MARKER.exit_tid=tid>0?(U)tid:0;
    return MARKER.restore_rc=handoff.initialized?frame_handoff_restore(&handoff):0;
}
API int IM_SAMPLE_SO_sus(void){MARKER.suspend++;return 0;}
API int IM_SAMPLE_SO_res(void){MARKER.resume++;return 0;}
API int IM_SAMPLE_SO_inact(void){MARKER.inactive++;return 0;}
API int IM_SAMPLE_SO_act(void){MARKER.active++;return 0;}

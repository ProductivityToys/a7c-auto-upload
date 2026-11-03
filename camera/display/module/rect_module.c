/* ILCE-7C 2.00: native rectangles at the observed idle gain boundary.
 * Default: restore slot before one draw. SERIES: redraw 20/42/80 percent for
 * at most 9 seconds or 1200 frames, gate new work and restore slot on stop.
 * Always forward original gain; no font, timer, worker or persistent changes.
 * External controller drains/retire then requests native redraw on exit.
 * Retain immutable mapping for late-fetched callbacks until boot ends. */
#ifdef A7C_RECT_SERIES_TRIAL
#include "frame_series.h"
#else
#include "frame_handoff.h"
#endif
#include "event_state.h"
typedef unsigned U;
typedef unsigned short H;
extern int syscall(int,...);
extern int TextRM_loadFont(const char *,U *); /* address anchor only */
#define API __attribute__((visibility("default")))
#include "native_rect_bar.h"
#ifdef A7C_RECT_SERVICE_TRIAL
#include "rect_service.h"
static struct rect_service service;
static U owner_checked,owner_seen;static int owner_alive;
#elif defined(A7C_RECT_UPLOAD_TRIAL)
#include "rect_progress.h"
static struct rect_progress progress;
#endif
API struct { struct event_marker event; U target,outer; int draw_rc;
#ifdef A7C_RECT_SERIES_TRIAL
    U frames,changes,percent,stopped,started_ms;
#ifdef A7C_RECT_UPLOAD_TRIAL
    U command;
#ifdef A7C_RECT_SERVICE_TRIAL
    U owner,health;
#endif
#endif
#endif
} a7c_native_marker={
#ifdef A7C_RECT_SERVICE_TRIAL
    .event={.magic=0x41374d31,.version=21,.prepare_rc=-999,.restore_rc=-999,.capture_rc=-999},
#elif defined(A7C_RECT_UPLOAD_TRIAL)
    .event={.magic=0x41374d31,.version=18,.prepare_rc=-999,.restore_rc=-999,.capture_rc=-999},
#elif defined(A7C_RECT_SERIES_TRIAL)
    .event={.magic=0x41374d31,.version=17,.prepare_rc=-999,.restore_rc=-999,.capture_rc=-999},
#else
    .event={.magic=0x41374d31,.version=16,.prepare_rc=-999,.restore_rc=-999,.capture_rc=-999},
#endif
    .draw_rc=-999};
#define MARKER a7c_native_marker.event
#ifdef A7C_RECT_SERIES_TRIAL
static struct frame_series handoff;
#else
static struct frame_handoff handoff;
#endif
static int pointer(U p){return p>=0x10000&&p<0x7fff0000&&!(p&3);}
static int draw(U base,U percent){
#ifdef A7C_RECT_SERVICE_TRIAL
    if(*(unsigned char *)(base+0x145aae4+204))return -17;
#endif
    U *manager=(void *)(base+0x1453df0),*outer=(void *)*(U *)(base+0x1453918);
    if(!pointer((U)outer)||outer[0]!=base+0x13b68c0||manager[0x58/4]!=1)return -10;
    U *delegate=(void *)outer[4];
    if(!pointer((U)delegate)||delegate[0]!=base+0x13b6648)return -11;
    U *window=(void *)delegate[0x164/4],*surface=(void *)delegate[0x16c/4];
    if(!pointer((U)window)||!pointer((U)surface)||window[0]!=base+0x13b3da0||
       window[1]!=0xcefacade||surface[0x6c/4]!=(U)window||surface[2]!=1)return -12;
    U *vector=(void *)window[0xb0/4],front=manager[0x8c/4];
    U bytes=window[0xb4/4]-(U)vector,index=window[0xbc/4];
    if(!pointer((U)vector)||!pointer(front))return -13;
#if defined(A7C_RECT_SERVICE_TRIAL) && !defined(A7C_SERVICE_SINGLE_BUFFER)
    /* The native window selects its DRAW buffer; DDS exposes the last front.
     * Photo live view has two ordinary RAM buffers and flips index each frame.
     * Keep the observed single aperture path, and accept only the verified
     * two-entry type-2 window. All drawing still goes through native methods. */
    int double_buffer=bytes==16;
    if(double_buffer){
        if(index>1||vector[1]!=2||vector[3]!=2||
           (front!=vector[0]&&front!=vector[2]))return -13;
        front=vector[index*2];if(!pointer(front))return -13;
    }else
#endif
    if(bytes!=8||index||vector[0]!=front)return -13;
    U *bitmap=(void *)front,*desc=(void *)bitmap[1];
    if(bitmap[0]!=base+0x13b1f50||!pointer((U)desc)||!pointer(bitmap[2])||
       desc[4]!=0x01e00280||desc[6]!=desc[4]||desc[7]!=1)return -14;
#if defined(A7C_RECT_SERVICE_TRIAL) && !defined(A7C_SERVICE_SINGLE_BUFFER)
    if(double_buffer){
        if(desc[9]<0x20000000U||desc[9]>0x3ff69000U||(desc[9]&4095))return -14;
    }else
#endif
    if(desc[9]!=0xfe33a000)return -14;
    /* This trial uses unrotated native 640x480 coordinates and neutral gain.
     * Gain's dirty-region mask therefore does not alter the added rectangle. */
    if(*(H *)(base+0x1453978)!=640||*(H *)(base+0x1453964)!=480||
       *(U *)(base+0x145396c)||*(U *)(base+0x1453970)||*(U *)(base+0x1453974)||
       *(unsigned char *)(base+0x13e5b61)!=100||*(unsigned char *)(base+0x13e5b62)!=100)return -15;
#if defined(A7C_RECT_SERIES_TRIAL) && !defined(A7C_RECT_SERVICE_TRIAL)
    if(a7c_native_marker.frames&&(a7c_native_marker.target!=front||a7c_native_marker.outer!=(U)outer))return -16;
#endif
    a7c_native_marker.target=front;a7c_native_marker.outer=(U)outer;
    return native_rect_bar_owned(base,outer,percent);
}
static void capture(void){
    U ts[2]={0,0};int tid=syscall(224),rc=syscall(263,1,ts);
#ifdef A7C_RECT_SERIES_TRIAL
    if(tid<=0||rc||ts[1]>=1000000000U||(MARKER.tid&&MARKER.tid!=(U)tid)){
        MARKER.capture_rc=a7c_native_marker.draw_rc=-20;
        a7c_native_marker.stopped=2;series_stop(&handoff);
        __atomic_store_n(&MARKER.captured,1,__ATOMIC_RELEASE);return;
    }
    U now=ts[0]*1000+ts[1]/1000000U;
#ifdef A7C_RECT_SERVICE_TRIAL
    U percent=100,owner=__atomic_load_n(&a7c_native_marker.owner,__ATOMIC_ACQUIRE);
    if(owner&&(owner!=owner_seen||now-owner_checked>=1000U)){
        owner_alive=syscall(37,owner,0)==0;owner_seen=owner;owner_checked=now;
    }
    int step=rect_service_step(&service,owner,owner_alive,
              __atomic_load_n(&a7c_native_marker.command,__ATOMIC_ACQUIRE),
              __atomic_load_n(&a7c_native_marker.health,__ATOMIC_ACQUIRE),now,&percent);
    a7c_native_marker.started_ms=service.started;
    if(step<=0){
        if(step<0){a7c_native_marker.stopped=1;series_stop(&handoff);}
        if(a7c_native_marker.percent!=101){
            volatile unsigned char *counter=(void *)((U)&TextRM_loadFont-0x57d271+0x14539b4);
            if(*counter<2)*counter=2;
            a7c_native_marker.percent=101;
        }
        MARKER.capture_rc=0;__atomic_store_n(&MARKER.captured,1,__ATOMIC_RELEASE);return;
    }
#elif defined(A7C_RECT_UPLOAD_TRIAL)
    U percent=0;
    int step=rect_progress_step(&progress,__atomic_load_n(&a7c_native_marker.command,__ATOMIC_ACQUIRE),now,&percent);
    a7c_native_marker.started_ms=progress.started;
    if(step<=0){
        if(step<0){a7c_native_marker.stopped=(U)-step;series_stop(&handoff);}
        MARKER.capture_rc=step==-2?-22:0;
        __atomic_store_n(&MARKER.captured,1,__ATOMIC_RELEASE);return;
    }
#else
    if(!a7c_native_marker.frames)a7c_native_marker.started_ms=now;
    U elapsed=now-a7c_native_marker.started_ms;
    if(elapsed>=9000||a7c_native_marker.frames>=1200){
        a7c_native_marker.stopped=1;series_stop(&handoff);return;
    }
    U percent=elapsed<3000?20:elapsed<6000?42:80;
#endif
#else
    U percent=42;
#endif
    MARKER.tid=tid>0?(U)tid:0;MARKER.sec=ts[0];MARKER.nsec=ts[1];
    if(tid<=0||rc||ts[1]>=1000000000U)rc=-20;
    else rc=draw((U)&TextRM_loadFont-0x57d271,percent);
    a7c_native_marker.draw_rc=rc;MARKER.capture_rc=rc;
#ifdef A7C_RECT_SERIES_TRIAL
#ifdef A7C_RECT_SERVICE_TRIAL
    if(rc){MARKER.capture_rc=0;__atomic_store_n(&MARKER.captured,1,__ATOMIC_RELEASE);return;}
    /* Request a full native repaint only when switching between icon and bar.
     * The hook draws after native scene composition, before presentation. */
    if(a7c_native_marker.frames&&a7c_native_marker.percent!=percent&&
       (a7c_native_marker.percent>=100||percent>=100)){
        volatile unsigned char *counter=(void *)((U)&TextRM_loadFont-0x57d271+0x14539b4);
        if(*counter<2)*counter=2;
    }
#endif
    if(rc){a7c_native_marker.stopped=2;series_stop(&handoff);}
    else {
        if(!a7c_native_marker.frames||a7c_native_marker.percent!=percent)a7c_native_marker.changes++;
        a7c_native_marker.percent=percent;a7c_native_marker.frames++;
    }
#endif
    __atomic_store_n(&MARKER.captured,1,__ATOMIC_RELEASE);
}
#ifdef A7C_RECT_SERIES_TRIAL
static void gain_entry(void){series_enter(&handoff);}
#else
static void gain_entry(void){frame_handoff_enter(&handoff);}
#endif
API int IM_SAMPLE_SO_init(void){
    if(MARKER.init++)return -1;
    U base=(U)&TextRM_loadFont-0x57d271;
    const unsigned char expected[16]={0x43,0x4b,0x90,0xb5,0x85,0xb0,0x7b,0x44,
                                      0x02,0xaf,0x1b,0x78,0x64,0x2b,0x04,0xd1};
    int rc=-2;
    if(base<0x1000000U||base>0x70000000U||(base&4095))goto done;
    for(U i=0;i<16;i++)if(*(const unsigned char *)(base+0x675278+i)!=expected[i])goto done;
    U table=*(U *)(base+0x1453914);if(table!=base+0x14539d8)goto done;
    MARKER.view=table;MARKER.internal=table;MARKER.slot=table+0x5c;MARKER.original=base+0x675279;
    int tid=syscall(224);if(tid<=0)goto done;MARKER.init_tid=(U)tid;
#ifdef A7C_RECT_SERIES_TRIAL
    rc=series_prepare(&handoff,(void *)(table+0x5c),
#else
    rc=frame_handoff_prepare(&handoff,(void *)(table+0x5c),
#endif
                            (void *)(base+0x675279),gain_entry,capture);
done:MARKER.prepare_rc=rc;return rc;
}
API int IM_SAMPLE_SO_exit(void){
    if(MARKER.exit++)return MARKER.restore_rc;
    int tid=syscall(224);MARKER.exit_tid=tid>0?(U)tid:0;
#ifdef A7C_RECT_SERIES_TRIAL
    int rc=handoff.initialized?series_stop(&handoff):0;
    /* Exit runs in IM's module thread, not Appframework. Drain only existing
     * draw work; no sleeps or polling ever run in the drawing callback. */
    for(U i=0;rc==1&&i<50;i++){
        U delay[2]={0,10000000};syscall(162,delay,0);
        rc=series_stop(&handoff);
    }
    return MARKER.restore_rc=rc;
#else
    return MARKER.restore_rc=handoff.initialized?frame_handoff_restore(&handoff):0;
#endif
}
#ifdef A7C_RECT_SERIES_TRIAL
static int pause_drawing(U reason){
    if(!handoff.initialized)return 0;
    int rc=series_pause(&handoff,reason);
    /* IM invokes lifecycle callbacks outside Appframework. Close the draw gate
     * first, then drain an existing draw, using the same bound as module exit.
     * Never wait for our own draw if a native call reenters lifecycle handling. */
    U tid=(U)syscall(224);
    for(U i=0;rc==1&&tid!=MARKER.tid&&i<50;i++){
        U delay[2]={0,10000000};syscall(162,delay,0);
        rc=series_pause(&handoff,reason);
    }
    if(rc){
        /* Native IM ignores a callback error. Retire rather than automatically
         * reopen after a draw that could not be drained within the bound. */
        a7c_native_marker.stopped=2;
        MARKER.restore_rc=series_stop(&handoff);MARKER.capture_rc=-23;
        /* Retirement rechecks busy after closing the gate/restoring the slot.
         * A draw can finish between the final pause check and that recheck.
         * Report the final state so an already-drained inact sends its ACK;
         * do not leave IM pending on a stale busy result. */
        if(rc==1)rc=MARKER.restore_rc;
    }
    return rc;
}
#endif
API int IM_SAMPLE_SO_sus(void){
    MARKER.suspend++;
#ifdef A7C_RECT_SERIES_TRIAL
    return pause_drawing(SERIES_SLEEP);
#else
    return 0;
#endif
}
API int IM_SAMPLE_SO_res(void){
    MARKER.resume++;
#ifdef A7C_RECT_SERIES_TRIAL
    return handoff.initialized?series_resume(&handoff,SERIES_SLEEP):0;
#else
    return 0;
#endif
}
#ifdef A7C_SERVICE_LIFECYCLE_ACK
static int lifecycle_complete(U operation,int transition_rc){
    /* Type 0x20000003 act/inact are asynchronous IM contracts. The dlsym
     * wrapper discards our return value; only a queued completion releases
     * IM's pending count. Reuse Sony's 16-byte async sender, with OUR module
     * ID (2031), not InfraMediaPwrMgr's ID. Never send sync IPC to this thread.
     * Firmware SHA and sender bytes are pinned by the offline build/lab.
     * No notification for sus/res: those dispatchers add no pending count. */
    if(transition_rc)return transition_rc;
    U base=(U)&TextRM_loadFont-0x57d271;
    int rc=((int (*)(U,U))(base+0x930c89))(operation,2031);
    if(rc){
        a7c_native_marker.stopped=2;
        MARKER.restore_rc=handoff.initialized?series_stop(&handoff):0;
        MARKER.capture_rc=-24;
    }
    return rc;
}
#endif
API int IM_SAMPLE_SO_inact(void){
    MARKER.inactive++;
#ifdef A7C_RECT_SERIES_TRIAL
#ifdef A7C_SERVICE_LIFECYCLE_ACK
    return lifecycle_complete(0x940122,pause_drawing(SERIES_INACTIVE));
#else
    return pause_drawing(SERIES_INACTIVE);
#endif
#else
    return 0;
#endif
}
API int IM_SAMPLE_SO_act(void){
    MARKER.active++;
#ifdef A7C_RECT_SERIES_TRIAL
#ifdef A7C_SERVICE_LIFECYCLE_ACK
    return lifecycle_complete(0x940123,handoff.initialized?series_resume(&handoff,SERIES_INACTIVE):0);
#else
    return handoff.initialized?series_resume(&handoff,SERIES_INACTIVE):0;
#endif
#else
    return 0;
#endif
}

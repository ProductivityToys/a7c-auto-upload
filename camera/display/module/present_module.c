/* ILCE-7C 2.00 one-shot, after native presentation/completion. Private glyph
 * generated offline by TextRM. No font/bitmap allocations or threads.
 * Explicit sync trial adds one owned native EGL fence before the CPU copy.
 * External controller must validate page/blank ROI, exclude active upload,
 * retain immutable module mapping, and request a native redraw on retirement. */
#include "event_handoff.h"
#include "present_state.h"
#include "present_blit.h"
#include "present_glyph.h"
typedef unsigned U;
extern int syscall(int,...);
extern int TextRM_loadFont(const char *,U *); /* address anchor only */
#define API __attribute__((visibility("default")))
#ifdef PRESENT_ALIAS_TRIAL
#ifdef PRESENT_SYNC_TRIAL
#define PRESENT_VERSION 14
#include "present_sync.h"
#else
#define PRESENT_VERSION 13
#endif
extern int open(const char *,int,...),close(int),munmap(void *,unsigned);
extern void *mmap64(void *,unsigned,int,int,int,long long);
static const volatile unsigned short *physical_alias;
static int alias_prepare(void) {
    int f=open("/dev/mem",0);if(f<0)return -1;
    void *p=mmap64(0,614400,1,1,f,0xfe33a000LL);
    int failed=close(f);
    if(p==(void *)-1)return -1;
    if(failed){munmap(p,614400);return -1;}
    physical_alias=p; /* address retained after publication */
    return 0;
}
static unsigned alias_ink(unsigned *matched) {
    unsigned ink=0;*matched=0;
    for(U y=0;y<20;y++)for(U x=0;x<78;x++) {
        unsigned short got=physical_alias[(432+y)*640+562+x];
        unsigned short want=x<71?present_glyph[y*71+x]:0;
        if(got)ink++;
        if(got==want)(*matched)++;
    }
    return ink;
}
#else
#define PRESENT_VERSION 12
#endif
API struct present_marker a7c_native_marker={.event={.magic=0x41374d31,.version=PRESENT_VERSION,
    .prepare_rc=-999,.restore_rc=-999,.capture_rc=-999}};
static struct event_handoff handoff;
static U obj_base;
static int pointer(U p){return p>=0x10000&&p<0x7fff0000&&!(p&3);}
#ifdef PRESENT_SYNC_TRIAL
static int synchronize(void) {
    U *outer=(void *)*(U *)(obj_base+0x1453918);
    if(!pointer((U)outer)||outer[0]!=obj_base+0x13b68c0)return -15;
    U *inner=(void *)outer[4];
    if(!pointer((U)inner)||inner[0]!=obj_base+0x13b6648||
       inner[0x168/4]!=1||!inner[0x170/4])return -15;
    U before[2],after[2];
    if(syscall(263,1,before))return -22;
    struct present_sync_result s;
    int rc=present_sync_once(obj_base,inner[0x168/4],&s);
    a7c_native_marker.sync_rc=rc;
    a7c_native_marker.sync_created=s.created;a7c_native_marker.sync_wait=s.wait_result;
    a7c_native_marker.sync_poll=s.poll_result;a7c_native_marker.sync_destroy=s.destroy_result;
    if(syscall(263,1,after))return -22;
    a7c_native_marker.sync_elapsed_us=(after[0]-before[0])*1000000U+
                                     after[1]/1000U-before[1]/1000U;
    return rc?-20:0;
}
#endif
static int compose(void) {
    U base=obj_base;
    U *manager=(void *)(base+0x1453df0),*outer=(void *)*(U *)(base+0x1453918);
    if(!pointer((U)outer)||outer[0]!=base+0x13b68c0||manager[0x58/4]!=1)return -10;
    U *delegate=(void *)outer[4];
    if(!pointer((U)delegate)||delegate[0]!=base+0x13b6648)return -11;
    U *window=(void *)delegate[0x164/4],*surface=(void *)delegate[0x16c/4];
    if(!pointer((U)window)||!pointer((U)surface)||window[0]!=base+0x13b3da0||
       window[1]!=0xcefacade||surface[0x6c/4]!=(U)window||surface[2]!=1)return -12;
    U *vector=(void *)window[0xb0/4],front=manager[0x8c/4];
    if(!pointer((U)vector)||window[0xb4/4]-(U)vector!=8||window[0xbc/4]||vector[0]!=front||!pointer(front))return -13;
    U *bitmap=(void *)front,*desc=(void *)bitmap[1];
    if(bitmap[0]!=base+0x13b1f50||!pointer((U)desc)||!pointer(bitmap[2])||
       desc[4]!=0x01e00280||desc[6]!=desc[4]||desc[7]!=1||desc[9]!=0xfe33a000)return -14;
    a7c_native_marker.target=front;a7c_native_marker.pixels=bitmap[2];
#ifdef PRESENT_ALIAS_TRIAL
    unsigned ignored;
    a7c_native_marker.alias=(U)physical_alias;
    a7c_native_marker.alias_before=alias_ink(&ignored);
#endif
    int rc=present_blit((void *)bitmap[2],present_glyph,&a7c_native_marker.before_ink,
                        &a7c_native_marker.after_ink,&a7c_native_marker.matched);
#ifdef PRESENT_ALIAS_TRIAL
    a7c_native_marker.alias_after=alias_ink(&a7c_native_marker.alias_matched);
#endif
    return rc;
}
static void capture(void) {
    struct event_marker *m=&a7c_native_marker.event;
    U ts[2]={0,0};int tid=syscall(224),rc=syscall(263,1,ts);
    m->tid=tid>0?(U)tid:0;m->sec=ts[0];m->nsec=ts[1];
    a7c_native_marker.original_completed=1;
    m->capture_rc=-1;
    if(tid>0&&!rc&&ts[1]<1000000000U) {
#ifdef PRESENT_SYNC_TRIAL
        rc=synchronize();
        /* Re-resolve the current surface/front after the native wait. */
        m->capture_rc=rc?rc:compose();
#else
        m->capture_rc=compose();
#endif
    }
    __atomic_store_n(&m->captured,1,__ATOMIC_RELEASE);
}
static void present_entry(void *arg){event_handoff_enter_after(&handoff,arg);}
API int IM_SAMPLE_SO_init(void) {
    struct event_marker *m=&a7c_native_marker.event;
    if(m->init++)return -1;
    U base=(U)&TextRM_loadFont-0x57d271;int rc=-2;
    if(base<0x1000000U||base>0x70000000U||(base&4095))goto done;
    /* Host pins full firmware; verify the exact dispatch and original entry
     * in-process as well. No replacement of a foreign callback or argument. */
    const unsigned char call[16]={0x09,0x4b,0x7b,0x44,0x1b,0x68,0x1b,0xb1,0x08,0x48,0x78,0x44,0x00,0x68,0x98,0x47};
    for(U i=0;i<16;i++)if(*(const unsigned char *)(base+0x7e697c+i)!=call[i])goto done;
    const unsigned char original[16]={0x05,0x48,0x80,0xb5,0x78,0x44,0x00,0x68,0x00,0xaf,0x18,0xb1,0xbd,0xe8,0x80,0x40};
    for(U i=0;i<16;i++)if(*(const unsigned char *)(base+0x675084+i)!=original[i])goto done;
    if(*(U *)(base+0x145abe8))goto done;
    m->slot=base+0x145abe4;m->original=base+0x675085;
    m->view=base+0x1453918;m->internal=base+0x1453df0;obj_base=base;
    int tid=syscall(224);if(tid<=0)goto done;m->init_tid=(U)tid;
#ifdef PRESENT_ALIAS_TRIAL
    if(alias_prepare()){rc=-3;goto done;}
#endif
    rc=event_handoff_prepare(&handoff,(void *)m->slot,(void *)m->original,present_entry,capture);
#ifdef PRESENT_ALIAS_TRIAL
    /* Failed publication cannot have a captured caller. Successful publication
     * retains the read-only alias with immutable code for a committed callback. */
    if(rc){munmap((void *)physical_alias,614400);physical_alias=0;}
#endif
done:
    m->prepare_rc=rc;return rc;
}
API int IM_SAMPLE_SO_exit(void) {
    struct event_marker *m=&a7c_native_marker.event;
    if(m->exit++)return m->restore_rc;
    int tid=syscall(224);m->exit_tid=tid>0?(U)tid:0;
    return m->restore_rc=handoff.initialized?event_handoff_restore(&handoff):0;
}
API int IM_SAMPLE_SO_sus(void){a7c_native_marker.event.suspend++;return 0;}
API int IM_SAMPLE_SO_res(void){a7c_native_marker.event.resume++;return 0;}
API int IM_SAMPLE_SO_inact(void){a7c_native_marker.event.inactive++;return 0;}
API int IM_SAMPLE_SO_act(void){a7c_native_marker.event.active++;return 0;}

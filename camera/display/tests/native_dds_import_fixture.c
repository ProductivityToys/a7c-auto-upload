/* Actual observer DSO and original DDS raster/submit, isolated ARM only.
 * Driver/bitmap boundaries simulated. Imports are redirected via actual GOT
 * relocations by the DSO; no Thumb instruction patch is used by the observer. */
typedef unsigned U;
typedef unsigned short H;
#include "../module/dds_import_handoff.h"
extern int printf(const char *,...),mprotect(void *,unsigned,int),syscall(int,...);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern void __clear_cache(void *,void *);
extern unsigned alarm(unsigned);
extern int fork(void),waitpid(int,int *,int),fflush(void *);
extern void _exit(int);
struct sample {U ready,kind,caller,tid,source,target,src_size,dst_xy,dst_size;int original_rc;};
struct marker {
    U magic,version,init,exit,suspend,resume,inactive,active;
    int prepare_rc,install_rc,restore_rc;U count;struct sample samples[8];
};
static U source,front,locked,held,refs,bad,unlock_calls,submit_calls,expected_foreign;
static H pixels[288*32],source_rect[4]={0,0,288,32},front_rect[4]={0,0,640,480};
static int unlock_rc,submit_rc;
static int lock(void *bitmap,int timeout,void **out) {
    if(bitmap!=&source||timeout!=-1||locked)bad=1;
    locked=1;*out=pixels;return 0;
}
static int unlock(void *bitmap) {
    unlock_calls++;if(bitmap!=&source||!locked)bad=1;locked=0;return unlock_rc;
}
static int enter(void){if(held)bad=1;held=1;return 0;}
static int leave(void){if(!held)bad=1;held=0;return 0;}
static int acquire(void **out){if(!held)bad=1;*out=&front;return 0;}
static int retain(void *p){if(p!=&front||!held)bad=1;refs++;return 0;}
static int release(void *p){if(p!=&front||held||refs!=1)bad=1;refs--;return 0;}
static int rectangle(void *p,H **out) {
    if(p==&source)*out=source_rect;
    else if(p==&front)*out=front_rect;
    else {bad=1;return -1;}
    return 0;
}
static int submit(U a,U b,const U *desc,U callback,U argument) {
    submit_calls++;
    if(expected_foreign) {
        if(a!=11||b!=12||desc!=(void *)&source||callback!=13||argument!=14)bad=1;
    } else {
        const U expected[20]={(U)&source,0,(32U<<16)|288,(U)&front,
            (432U<<16)|562,(192U<<16)|576,0,(480U<<16)|640,1,255,
            0,0,0,0,0,0x3f800000,0x3f800000,0,0,0};
        if(a||b||callback||argument||held||refs!=1)bad=1;
        for(U i=0;i<20;i++)if(desc[i]!=expected[i])bad=1;
    }
    return submit_rc;
}
static int replace(U address,void *callback) {
    U page=address&~4095U;if(mprotect((void *)page,8192,7))return 1;
    H *code=(H *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *p=(void *)(address+4);U dest=(U)callback;
    for(U i=0;i<4;i++)p[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5)!=0;
}
static int pair_cases(void) {
    for(U mode=0;mode<5;mode++) {
        struct dds_import_handoff h={0};U slots[2]={101,102};
        if(dds_import_prepare(&h,slots,slots+1,101,102,101,102,201,202))return 1;
        if(mode==1)slots[0]=301;
        if(mode==2)slots[1]=302;
        int rc=dds_import_install(&h);
        if(mode==1||mode==2) {
            if(rc!=-2||h.enabled||slots[0]!=(mode==1?301U:101U)||slots[1]!=(mode==2?302U:102U))return 2;
        } else {
            if(rc||!h.enabled||slots[0]!=201||slots[1]!=202)return 3;
            if(mode==3)slots[0]=301;
            if(mode==4)slots[1]=302;
            U result=dds_import_restore(&h);
            if(result!=(mode==3?1U:mode==4?2U:0U)||h.enabled||
                slots[0]!=(mode==3?301U:101U)||slots[1]!=(mode==4?302U:102U))return 4;
            if(dds_import_restore(&h)!=result)return 5;
        }
    }
    printf("DDS_IMPORT_PAIR_OK 5 partial_install_rollback foreign_slots_preserved\n");return 0;
}
static int run_case(unsigned lazy) {
    alarm(15);if(pair_cases())return 1;
    void *native=dlopen("/lab/libObj.so",1);if(!native)return 2;
    U anchor=(U)dlsym(native,"TextRM_loadFont");if(!anchor)return 3;
    U base=anchor-0x57d271;
    if(replace(base+0x68dc28,lock)||replace(base+0x68dc38,unlock)||
       replace(base+0x68ce02,submit)||replace(base+0x68db58,rectangle)||
       replace(base+0x75ccf4,enter)||replace(base+0x75cce4,leave)||
       replace(base+0x75cca4,acquire)||replace(base+0x68dc48,retain)||
       replace(base+0x68dc58,release))return 4;
    int (*raster)(U,void *,void *)=(void *)(base+0x7db4a1);
    int (*scaled_submit)(U,U,void *,void *)=(void *)(base+0x7db519);
    U slots[24]={0};H xy[2]={562,432};
    /* Resolve both real imports before any observer installation. */
    if(raster(0,slots,&source)||scaled_submit(0,0,&source,xy)||bad)return 5;
    U *unlock_slot=(void *)(base+0x13d08dc),*submit_slot=(void *)(base+0x13d0640);
    if(*unlock_slot!=base+0x68dc39||*submit_slot!=base+0x68ce03)return 6;
    if(lazy)__atomic_store_n(submit_slot,base+0x1076b4,__ATOMIC_RELEASE);
    U saved_native_submit=*submit_slot;
    void *module=dlopen("/trial/marker.so",2);if(!module)return 7;
    int (*start)(void)=dlsym(module,"IM_SAMPLE_SO_init");
    int (*stop)(void)=dlsym(module,"IM_SAMPLE_SO_exit");
    struct marker *m=dlsym(module,"a7c_native_marker");
    if(!start||!stop||!m||m->version!=15||start())return 8;
    U saved_unlock=*unlock_slot,saved_submit=*submit_slot;
    if(saved_unlock==base+0x68dc39||saved_submit==base+0x68ce03)return 9;
    int (*call_unlock)(void *)=(void *)saved_unlock;
    int (*call_submit)(U,U,const U *,U,U)=(void *)saved_submit;
    U uc=unlock_calls,sc=submit_calls;
    locked=1;unlock_rc=-17;
    if(call_unlock(&source)!=-17||unlock_calls!=uc+1||m->count)return 10;
    expected_foreign=1;submit_rc=-19;
    if(call_submit(11,12,&source,13,14)!=-19||submit_calls!=sc+1||m->count||bad)return 11;
    expected_foreign=0;
    if(raster(0,slots,&source)!=(int)0xe0000002U||m->count!=1)return 12;
    struct sample *s=&m->samples[0];
    if(!s->ready||s->kind!=1||s->caller!=base+0x7db4fb||s->source!=(U)&source||
        s->original_rc!=-17||s->tid!=(U)syscall(224))return 13;
    if(scaled_submit(0,0,&source,xy)||m->count!=2)return 14;
    s=&m->samples[1];
    if(!s->ready||s->kind!=2||s->caller!=base+0x68d21f||s->source!=(U)&source||
        s->target!=(U)&front||s->src_size!=((32U<<16)|288)||s->dst_size!=((192U<<16)|576)||
        s->dst_xy!=((432U<<16)|562)||s->original_rc!=-19||s->tid!=(U)syscall(224))return 15;
    unlock_rc=submit_rc=0;
    for(U i=0;i<12;i++)if(raster(0,slots,&source)||scaled_submit(0,0,&source,xy))return 16;
    if(m->count!=8||bad||refs||held||locked)return 17;
    for(U i=0;i<288*32;i++)if(pixels[i])return 18;
    if(start()!=-1||stop()||*unlock_slot!=base+0x68dc39||*submit_slot!=saved_native_submit)return 19;
    /* Simulate pointers fetched before retirement, invoked after restoration. */
    uc=unlock_calls;sc=submit_calls;locked=1;expected_foreign=1;
    if(call_unlock(&source)||call_submit(11,12,&source,13,14)||m->count!=8||
       unlock_calls!=uc+1||submit_calls!=sc+1||bad||stop())return 20;
    expected_foreign=0;
    if(raster(0,slots,&source)||scaled_submit(0,0,&source,xy)||bad||m->count!=8)return 21;
    printf("DDS_IMPORT_BINDING lazy=%u restored=%08x\n",lazy,saved_native_submit);
    printf("NATIVE_DDS_IMPORT_OK samples=8 exact_callers=2 original_returns_preserved late_forwarding=2 restored=2 no_pixel_changes\n");
    return 0;
}

int main(void) {
    for(U mode=0;mode<2;mode++) {
        int child=fork();if(child<0)return 30;
        if(!child){int rc=run_case(mode);fflush(0);_exit(rc);}
        int status=0;if(waitpid(child,&status,0)!=child||status)return 31;
    }
    printf("NATIVE_DDS_BINDINGS_OK 2 resolved_and_lazy_exact_restore\n");
    return 0;
}

/* Actual one-shot DSO and native present dispatch in isolated ARM userspace.
 * Only the bottom presentation and original completion are intercepted.
 * Synthetic window/bitmap storage, no device, driver or network access. */
#include "../module/present_state.h"
#include "present_glyph.h"
typedef unsigned U;
typedef unsigned short H;
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern int printf(const char *,...),fork(void),waitpid(int,int *,int);
extern int mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
extern void _exit(int);
extern unsigned alarm(unsigned);
static U outer[5],inner[100],window[48],surface[29],vector[2],bitmap[3],desc[12];
static H pixels[640*480];
static U forwarded,bottom_calls,bad;
#ifdef PRESENT_ALIAS_TRIAL
#ifdef PRESENT_SYNC_TRIAL
#define PRESENT_CASES 18
#define PRESENT_VERSION 14
#else
#define PRESENT_CASES 12
#define PRESENT_VERSION 13
#endif
static U alias_scenario,alias_opens,alias_maps,alias_unmaps;
static H separate_alias[640*480];
extern int syscall(int,...);
int open(const char *path,int flags,...) {
    const char *want="/dev/mem";U i=0;while(path[i]&&path[i]==want[i])i++;
    if(!path[i]&&!want[i]) {
        if(flags)bad=1;alias_opens++;return alias_scenario==11?-1:477;
    }
    return syscall(5,path,flags,0);
}
int close(int fd){return fd==477?0:syscall(6,fd);}
void *mmap64(void *p,U size,int prot,int flags,int fd,long long offset) {
    if(fd!=477)return (void *)syscall(192,p,size,prot,flags,fd,(U)(offset>>12));
    if(p||size!=614400||prot!=1||flags!=1||offset!=0xfe33a000LL)bad=1;
    alias_maps++;return alias_scenario==10?(void *)-1:alias_scenario==9?(void *)separate_alias:(void *)pixels;
}
int munmap(void *p,U size) {
    if(p==pixels||p==separate_alias){if(size!=614400)bad=1;alias_unmaps++;return 0;}
    return syscall(91,p,size);
}
#else
#define PRESENT_CASES 9
#define PRESENT_VERSION 12
#endif
static struct present_marker *marker;
#ifdef PRESENT_SYNC_TRIAL
static U sync_scenario,sync_creates,sync_waits,sync_destroys;
static void *sync_create(U display,U type,const int *attributes) {
    if(display!=1||type!=0x30f9||attributes||!marker->original_completed||forwarded!=1)bad=1;
    sync_creates++;return sync_scenario==13?0:(void *)0x1234;
}
static U sync_wait(U display,void *sync,U flags,unsigned long long ns) {
    if(display!=1||sync!=(void *)0x1234||flags!=(sync_waits?0U:1U)||
       ns!=(sync_waits?0ULL:20000000ULL))bad=1;
    sync_waits++;
    if(sync_scenario==17)vector[0]=(U)desc;
    return sync_scenario==12||(sync_scenario==15&&sync_waits==2)?0x30f5:0x30f6;
}
static U sync_destroy(U display,void *sync) {
    if(display!=1||sync!=(void *)0x1234)bad=1;
    sync_destroys++;return sync_scenario==14?0:1;
}
#endif
static void original(void *arg){
    if(arg||(!forwarded&&marker->original_completed))bad=1;
    forwarded++;
}
static void foreign(void *arg){(void)arg;}
static int bottom(U display,U target){
    U expected_display=1;
#ifdef PRESENT_SYNC_TRIAL
    if(sync_scenario==16)expected_display=2;
#endif
    if(display!=expected_display||target!=(U)surface)bad=1;
    bottom_calls++;return 1;
}
static int intercept(U address,void *destination) {
    U page=address&~4095U;
    if(mprotect((void *)page,8192,7))return -1;
    H *code=(void *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *literal=(void *)(address+4);U dest=(U)destination;
    for(U i=0;i<4;i++)literal[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5);
}
static H want(U x,U y,U scenario,int drawn) {
    if(scenario==1&&x==639&&y==451)return 0x1234;
    if(drawn&&x>=562&&x<633&&y>=432&&y<452)return present_glyph[(y-432)*71+x-562];
    /* Nonblank sentinel outside the requested region catches stray writes. */
    if(x<562||y<432||y>=452)return 0x2345;
    return 0;
}
static int check(U scenario,int drawn) {
    for(U y=0;y<480;y++)for(U x=0;x<640;x++)
        if(pixels[y*640+x]!=want(x,y,scenario,drawn))return 1;
    return 0;
}
int main(void) {
    alarm(15);
    void *native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    U base=(U)dlsym(native,"TextRM_loadFont")-0x57d271;
    void *module=dlopen("/trial/marker.so",2);if(!module)return 2;
    int (*init)(void)=dlsym(module,"IM_SAMPLE_SO_init");
    int (*finish)(void)=dlsym(module,"IM_SAMPLE_SO_exit");
    marker=dlsym(module,"a7c_native_marker");
    if(!init||!finish||!marker||marker->event.version!=PRESENT_VERSION)return 3;
    for(U scenario=0;scenario<PRESENT_CASES;scenario++) {
        int child=fork();if(child<0)return 4;
        if(!child) {
            U behavior=scenario==9?0:scenario;
#ifdef PRESENT_SYNC_TRIAL
            sync_scenario=scenario;
            if(scenario>=12)behavior=0;
#endif
            int drawn=behavior==0;
#ifdef PRESENT_SYNC_TRIAL
            if(scenario>=12)drawn=0;
#endif
#ifdef PRESENT_ALIAS_TRIAL
            alias_scenario=scenario;
#endif
            struct event_marker *m=&marker->event;
            U *slot=(void *)(base+0x145abe4),*arg=(void *)(base+0x145abe8);
            U *manager=(void *)(base+0x1453df0);
            *slot=base+0x675085;*arg=0;
            *(U *)(base+0x1453918)=(U)outer;
            outer[0]=base+0x13b68c0;outer[4]=(U)inner;
            inner[0]=base+0x13b6648;inner[0x164/4]=(U)window;
            inner[0x168/4]=1;inner[0x16c/4]=(U)surface;
            inner[0x170/4]=0x12345678;
            window[0]=base+0x13b3da0;window[1]=0xcefacade;
            window[0xb0/4]=(U)vector;window[0xb4/4]=(U)(vector+2);
            surface[2]=1;surface[0x6c/4]=(U)window;
            manager[0x58/4]=1;manager[0x8c/4]=(U)bitmap;
            vector[0]=(U)bitmap;vector[1]=5;
            bitmap[0]=base+0x13b1f50;bitmap[1]=(U)desc;bitmap[2]=(U)pixels;
            desc[4]=desc[6]=0x01e00280;desc[7]=1;desc[9]=0xfe33a000;
            for(U y=0;y<480;y++)for(U x=0;x<640;x++)pixels[y*640+x]=want(x,y,scenario,0);
#ifdef PRESENT_ALIAS_TRIAL
            if(scenario==10||scenario==11) {
                if(init()!=-3||m->prepare_rc!=-3||finish()||m->captured||
                   *slot!=base+0x675085||check(scenario,0)||bad||alias_opens!=1||
                   alias_maps!=(scenario==10?1U:0U)||alias_unmaps)_exit(22);
                _exit(0);
            }
#endif
            if(scenario==7||scenario==8) {
                if(scenario==7)*slot=(U)foreign;else *arg=1;
                if(init()!=-2||m->prepare_rc!=-2||check(scenario,0))_exit(10);
                if(finish()!=(scenario==7?-2:0)||*slot!=(scenario==7?(U)foreign:base+0x675085))_exit(11);
#ifdef PRESENT_ALIAS_TRIAL
                if(bad||alias_opens!=(scenario==7?1U:0U)||alias_unmaps!=alias_opens)_exit(23);
#endif
                _exit(0);
            }
            if(init()||m->prepare_rc||!m->init_tid)_exit(12);
            void (*fetched)(void *)=(void *)*slot;
            if(intercept(base+0x675084,original)||intercept(base+0x78b730,bottom))_exit(13);
#ifdef PRESENT_SYNC_TRIAL
            if(intercept(base+0x785a70,sync_create)||intercept(base+0x785670,sync_wait)||
               intercept(base+0x7858e0,sync_destroy))_exit(26);
            if(scenario==16)inner[0x168/4]=2;
#endif
            if(scenario==2)desc[9]=0;
            if(scenario==3)vector[0]=(U)desc;
            if(scenario==4)surface[0x6c/4]=0;
            if(scenario==5&&finish())_exit(14);
            if(scenario==6){*slot=(U)foreign;if(finish()!=-2)_exit(15);}
            if(behavior>=5)fetched(0);
            else ((void (*)(void))(base+0x66dc05))();
            int expected=behavior==0?0:behavior==1?-3:behavior==2?-14:behavior==3?-13:-12;
#ifdef PRESENT_SYNC_TRIAL
            if(scenario>=12)expected=scenario==16?-15:scenario==17?-13:-20;
#endif
            if(behavior<5&&(m->captured!=1||m->capture_rc!=expected||
               m->tid!=m->init_tid||marker->original_completed!=1||bottom_calls!=1))_exit(16);
            if(behavior>=5&&(m->captured||bottom_calls))_exit(17);
            if(bad||forwarded!=1||check(scenario,drawn)||
               *slot!=(scenario==6?(U)foreign:base+0x675085))_exit(18);
            if(drawn&&(marker->before_ink||marker->after_ink!=469||marker->matched!=1560))_exit(19);
#ifdef PRESENT_ALIAS_TRIAL
            if(drawn&&(marker->alias_before||marker->alias_after!=(scenario==9?0U:469U)||
               marker->alias_matched!=(scenario==9?1091U:1560U)))_exit(24);
            if(alias_opens!=1||alias_maps!=1||alias_unmaps)_exit(25);
#endif
#ifdef PRESENT_SYNC_TRIAL
            U expected_create=behavior<5&&scenario!=16;
            U expected_destroy=expected_create&&scenario!=13;
            U expected_wait=expected_destroy?(scenario==12?1U:2U):0U;
            if(sync_creates!=expected_create||sync_destroys!=expected_destroy||sync_waits!=expected_wait)_exit(27);
            if(scenario>=12&&marker->after_ink)_exit(28);
#endif
            /* Previously fetched callback only forwards after one-shot removal. */
            fetched(0);
            if(forwarded!=2||check(scenario,drawn)||bad)_exit(20);
#ifdef PRESENT_SYNC_TRIAL
            if(sync_creates!=expected_create||sync_destroys!=expected_destroy||sync_waits!=expected_wait)_exit(29);
#endif
            if(behavior<5&&(finish()||m->restore_rc||m->exit!=1))_exit(21);
            _exit(0);
        }
        int status=0;
        if(waitpid(child,&status,0)!=child||status){printf("PRESENT_MODULE_FAIL scenario=%u status=%d\n",scenario,status);return 30+scenario;}
        printf("PRESENT_MODULE_CASE scenario=%u ok=1\n",scenario);
    }
    printf("NATIVE_PRESENT_MODULE_OK %u actual_dso native_present_dispatch original_first bounded_pixels no_camera\n",PRESENT_CASES);
    return 0;
}

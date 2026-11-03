/* Offline only. Execute Sony's actual scene-draw/post-draw ordering while
 * replacing graphics boundaries. No display, driver, camera or live hook. */
typedef unsigned U;
typedef unsigned short H;
extern int printf(const char *,...);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern int mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
extern unsigned alarm(unsigned);
extern int syscall(int,...);
extern int fork(void),waitpid(int,int *,int);
extern void _exit(int);
#include "../module/frame_observer.h"
#include "../module/event_handoff.h"
#include "../module/frame_handoff.h"
static struct frame_observer observation;
static struct event_handoff handoff;
static U event_internal[24],event_data[8],forwarded,captured,handoff_bad;
static void handoff_capture(void){captured++;}
static void original_event(void *event) {
    if(event!=event_data||event_internal[0x14/4]!=(U)original_event)handoff_bad=1;
    forwarded++;
}
static void handoff_entry(void *event){event_handoff_enter(&handoff,event);}
static struct frame_handoff gain_handoff;
static U gain_table[25],gain_calls,gain_samples,gain_bad,gain_expected;
static void gain_original(void){
    if(gain_table[0x5c/4]!=gain_expected)gain_bad=1;
    gain_calls++;
}
static void gain_capture(void){gain_samples++;}
static void gain_foreign(void){}
static void gain_entry(void){frame_handoff_enter(&gain_handoff);}
static int frame_observer_clock(U *sec,U *nsec) {
    U ts[2];int rc=syscall(263,1,ts); /* ARM clock_gettime(CLOCK_MONOTONIC) */
    if(rc)return -1;*sec=ts[0];*nsec=ts[1];return 0;
}
static int frame_observer_tid(U *tid) {
    int result=syscall(224);if(result<=0)return -1;*tid=(U)result;return 0;
}
static U engine[160],vtable[32],backend[1],events[32],count,bad;
static U retirement_window;
static void (*native_set_callback)(void *,void *);
static void (*native_set_enabled)(void *,int);
static U wrapped[5],delegate[100],state_vtable[3],restored;
static U simulated_graphics_state[13];
static void event(U n){if(count<32)events[count++]=n;else bad=1;}
static void start(void){event(1);}
static void before(void){event(2);}
static U *get_backend(void){return backend;}
static void bind(void *p,void *q){(void)p;(void)q;event(3);}
static void dirty(void *p,void *q){(void)p;(void)q;event(4);}
static void draw(void *p){(void)p;event(5);}
static void begin(void *p){
    if(p!=backend)bad=1;event(6);
    /* Deterministic interleaving after native gate checks, before its second
     * pointer load. Simulates cancellation without camera/driver access. */
    if(retirement_window)native_set_enabled(engine,0);
    if(retirement_window==2)native_set_callback(engine,0);
    if(retirement_window==3)frame_observer_stop(&observation);
}
static void callback(void){event(7);}
static void observe_callback(void){event(7);frame_observer_tick(&observation);}
static void end(void *p){if(p!=backend)bad=1;event(8);}
static void flush(void *p){if(p!=backend)bad=1;event(9);}
static U present_display,present_surface,present_success;
static int present_boundary(U display,U surface) {
    if(display!=present_display||surface!=present_surface)bad=1;
    event(10);return (int)present_success;
}
static void after_present(void *arg){if((U)arg!=0x12345678)bad=1;event(11);}
static struct event_handoff present_handoff;
static void present_original(void *arg){after_present(arg);}
static void present_capture(void){event(12);}
static void present_entry(void *arg){event_handoff_enter_after(&present_handoff,arg);}
static int restore_state(U *p,U index,U value) {
    if(p!=delegate+0x28/4||index!=restored||index>=13||value!=100+index)bad=1;
    if(index<13)simulated_graphics_state[index]=value;
    restored++;return 1;
}
static int replace(U address,void *callback_) {
    U page=address&~4095U;
    if(mprotect((void *)page,8192,7))return 1;
    H *code=(H *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *literal=(void *)(address+4);U dest=(U)callback_;
    for(U i=0;i<4;i++)literal[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5)!=0;
}
#include "native_rect_boundary.h"
#include "native_rect_state.h"
#include "native_rect_backend.h"
int main(void) {
    alarm(10);
    void *native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    U symbol=(U)dlsym(native,"TextRM_loadFont");if(!symbol)return 2;
    U base=symbol-0x57d271;
    if(replace(base+0x66ddac,start)||replace(base+0x618126,before)||
       replace(base+0x66dd9c,get_backend)||replace(base+0x7e0408,bind)||
       replace(base+0x608e68,dirty)||replace(base+0x7e049a,draw))return 3;
    backend[0]=(U)vtable;vtable[0x2c/4]=(U)begin;
    vtable[0x30/4]=(U)end;vtable[0x1c/4]=(U)flush;
    void (*set_callback)(void *,void *)=(void *)(base+0x61805b);
    void (*set_enabled)(void *,int)=(void *)(base+0x61806f);
    native_set_callback=set_callback;native_set_enabled=set_enabled;
    void (*scene)(void *,void *)=(void *)(base+0x61819d);
    void (*post)(void *)=(void *)(base+0x6180d7);
    /* 2x2 gate matrix through the full scene path and direct post path.
     * Assert begin/callback/end/flush ordering, including no work when gated. */
    for(U direct=0;direct<2;direct++)for(U enabled=0;enabled<2;enabled++)for(U present=0;present<2;present++) {
        for(U i=0;i<160;i++)engine[i]=0;
        set_callback(engine,present?(void *)callback:0);set_enabled(engine,(int)enabled);
        if(engine[0x22c/4]!=(present?(U)callback:0)||((unsigned char *)engine)[0x231]!=enabled)return 4;
        count=bad=0;
        if(direct)post(engine);else scene(engine,0);
        U prefix=direct?0:5,tail=enabled&&present?4:0;
        if(bad||count!=prefix+tail)return 5;
        for(U i=0;i<prefix;i++)if(events[i]!=i+1)return 6;
        for(U i=0;i<tail;i++)if(events[prefix+i]!=i+6)return 7;
        printf("FRAME_ORDER direct=%u enabled=%u callback=%u events=",direct,enabled,present);
        for(U i=0;i<count;i++)printf("%u",events[i]);printf("\n");
    }
    /* Resolve and execute the actual wrapper/delegate virtual methods read
     * from firmware, not copies of their push/pop implementations. The final
     * state application is synthetic so this cannot reach GLES or a driver. */
    wrapped[0]=base+0x13b68c0;wrapped[4]=(U)delegate;
    delegate[0]=base+0x13b6648;
    U *state=delegate+0x28/4;state[0]=(U)state_vtable;
    state_vtable[2]=(U)restore_state;
    for(U i=0;i<13;i++)state[1+i]=100+i;
    U *methods=(U *)wrapped[0];
    int (*push_state)(void *)=(void *)methods[0x2c/4];
    int (*pop_state)(void *)=(void *)methods[0x30/4];
    bad=restored=0;
    if(push_state(wrapped)!=1||((unsigned char *)state)[0x7c]!=1)return 8;
    for(U i=0;i<13;i++)if(state[0x40/4+i]!=100+i)return 9;
    if(pop_state(wrapped)!=1||((unsigned char *)state)[0x7c]||restored!=13||bad)return 10;
    printf("NATIVE_FRAME_STATE_OK push_copies=13 pop_applies=13 active_cleared=1\n");
    /* Actual post-dispatch calls the passive core; native scope and final GPU
     * application above remain isolated. Kernel time/TID are this lab's, not
     * camera/UI evidence. No callback slot is changed on a real device. */
    if(frame_observer_arm(&observation,10))return 11;
    set_callback(engine,(void *)observe_callback);set_enabled(engine,1);
    for(U frame=0;frame<FO_SAMPLES;frame++) {
        count=bad=0;scene(engine,0);
        if(bad||count!=9)return 12;
        for(U i=0;i<9;i++)if(events[i]!=i+1)return 13;
    }
    struct frame_observer observed;
    if(frame_observer_snapshot(&observation,&observed)||observed.count!=FO_SAMPLES||
       observed.phase!=FO_FULL)return 14;
    for(U i=0;i<FO_SAMPLES;i++)if(!observed.samples[i].tid||
        observed.samples[i].tid!=observed.samples[0].tid)return 15;
    frame_observer_stop(&observation);count=bad=0;post(engine);
    if(frame_observer_snapshot(&observation,&observed)||observed.count!=FO_SAMPLES||
       observed.phase!=FO_STOPPED||bad||count!=4)return 16;
    printf("NATIVE_FRAME_OBSERVER_OK samples=%u state_bytes=%u same_lab_tid=1 stopped_late_call=1\n",
           observed.count,(U)sizeof observation);
    /* The real Event::getId and native default dispatcher are unmodified.
     * ID 0 takes the default branch, not any native layer/state mutation. */
    void (*event_dispatch)(void *,void *)=(void *)(base+0x89f58d);
    event_handler_fn *slot=(void *)(event_internal+0x14/4);
    *slot=original_event;
    if(event_handoff_prepare(&handoff,slot,original_event,handoff_entry,handoff_capture))return 17;
    event_handler_fn fetched=*slot;
    event_dispatch(event_internal,event_data);
    if(*slot!=original_event||forwarded!=1||captured!=1||handoff_bad)return 18;
    fetched(event_data); /* native dispatcher might have fetched before restore */
    event_dispatch(event_internal,event_data);
    if(forwarded!=3||captured!=1||handoff_bad||event_handoff_restore(&handoff))return 19;
    if(event_handoff_prepare(&handoff,slot,original_event,handoff_entry,handoff_capture)!=-1)return 20;
    *slot=(void *)(base+0x3ef545); /* actual live-identified handler, no-op for ID 0 */
    event_dispatch(event_internal,event_data);
    if(event_handoff_restore(&handoff)!=-2||*slot!=(void *)(base+0x3ef545))return 21;
    printf("NATIVE_EVENT_HANDOFF_OK original_forwarded=3 captures=1 restored_before_delegate=1 stale_wrapper=1 foreign_preserved=1\n");
    /* Disabling alone does not stop a dispatch already past the gate. */
    set_callback(engine,(void *)callback);set_enabled(engine,1);
    retirement_window=1;count=bad=0;post(engine);
    if(bad||count!=4||events[1]!=7||((unsigned char *)engine)[0x231])return 22;
    count=0;post(engine);if(count)return 23;
    printf("NATIVE_RETIRE_DISABLE late_callback=1 next_dispatch_gated=1\n");
    /* The unsafe disable+clear sequence must fault only in an isolated child.
     * This is actual native dispatcher execution, not a model of its loads. */
    int child=fork();if(child<0)return 24;
    if(!child){retirement_window=2;set_enabled(engine,1);post(engine);_exit(90);}
    int status=0;if(waitpid(child,&status,0)!=child||(status&127)!=11)return 25;
    printf("NATIVE_RETIRE_CLEAR null_call_signal=%d isolated_child=1\n",status&127);
    /* Retain a stopped, immutable callback: late dispatch completes its scope
     * but produces no new sample. This is logical stop, not full retirement. */
    struct frame_observer stopped={0};observation=stopped;
    if(frame_observer_arm(&observation,10))return 26;
    set_callback(engine,(void *)observe_callback);set_enabled(engine,1);
    retirement_window=3;count=bad=0;post(engine);
    if(frame_observer_snapshot(&observation,&observed)||observed.count||
       observed.phase!=FO_STOPPED||bad||count!=4||events[1]!=7)return 27;
    count=0;post(engine);if(count)return 28;
    printf("NATIVE_RETIRE_STOP retained_pointer=1 late_sample=0 native_scope_completed=1\n");
    /* Alternative: existing GraphicsSystem callback uses one pointer load.
     * Replace only the lab's table pointer, keep native dispatcher unmodified;
     * original gain is simulated, so no GPU/state/present work is performed. */
    U *gain_global=(void *)(base+0x1453914);U saved_gain_global=*gain_global;
    *gain_global=(U)gain_table;
    void (*native_gain_dispatch)(void)=(void *)(base+0x66de3d);
    for(U scenario=0;scenario<3;scenario++) {
        struct frame_handoff zero={0};gain_handoff=zero;
        gain_calls=gain_samples=gain_bad=0;
        gain_table[0x5c/4]=gain_expected=(U)gain_original;
        frame_handler_fn *slot=(void *)(gain_table+0x5c/4);
        if(frame_handoff_prepare(&gain_handoff,slot,gain_original,gain_entry,gain_capture))return 29;
        frame_handler_fn late=*slot;
        if(scenario==0)native_gain_dispatch();
        if(scenario==1&&frame_handoff_restore(&gain_handoff))return 30;
        if(scenario==2){
            *slot=gain_foreign;gain_expected=(U)gain_foreign;
            if(frame_handoff_restore(&gain_handoff)!=-2)return 31;
        }
        late();
        if(gain_bad||gain_calls!=(scenario==0?2U:1U)||gain_samples!=(scenario==0?1U:0U)||
           (U)*slot!=gain_expected)return 32;
        printf("NATIVE_GAIN_HANDOFF scenario=%u original_calls=%u captures=%u slot_preserved=1\n",
               scenario,gain_calls,gain_samples);
    }
    *gain_global=saved_gain_global;
    /* Execute the full native context +18 dispatch/delegation chain. Only the
     * bottom presentation boundary is replaced: no EGL/GPU/driver execution.
     * In particular its false return does NOT suppress the trailing callback,
     * so a trailing callback alone cannot certify a successful presentation. */
    if(replace(base+0x78b730,present_boundary))return 33;
    U *context_global=(void *)(base+0x1453918),saved_context=*context_global;
    U *after_slot=(void *)(base+0x145abe4),saved_after=*after_slot;
    U *after_arg=(void *)(base+0x145abe8),saved_arg=*after_arg;
    *context_global=(U)wrapped;*after_arg=0x12345678;
    present_display=1;present_surface=0x123400;
    delegate[0x168/4]=present_display;delegate[0x16c/4]=present_surface;
    void (*present)(void)=(void *)(base+0x66dc05);
    for(U trailing=0;trailing<2;trailing++)for(U success=0;success<2;success++) {
        *after_slot=trailing?(U)after_present:0;present_success=success;
        count=bad=0;present();
        if(bad||count!=1+trailing||events[0]!=10||(trailing&&events[1]!=11))return 34;
        printf("NATIVE_PRESENT_CHAIN success=%u trailing=%u arguments_preserved=1 events=%u\n",
               success,trailing,count);
    }
    for(U scenario=0;scenario<3;scenario++) {
        struct event_handoff zero={0};present_handoff=zero;
        *after_slot=(U)present_original;present_success=1;
        event_handler_fn *slot=(void *)after_slot;
        if(event_handoff_prepare(&present_handoff,slot,present_original,present_entry,present_capture))return 35;
        event_handler_fn late=*slot;
        if(scenario==1&&event_handoff_restore(&present_handoff))return 36;
        if(scenario==2){
            *slot=after_present;
            if(event_handoff_restore(&present_handoff)!=-2)return 37;
        }
        count=bad=0;present();
        if(bad||count!=(scenario==0?3U:2U)||events[0]!=10||events[1]!=11||
           (scenario==0&&events[2]!=12)||*slot!=(scenario==2?after_present:present_original))return 38;
        count=bad=0;late((void *)0x12345678);
        if(bad||count!=1||events[0]!=11)return 39;
        printf("NATIVE_PRESENT_HANDOFF scenario=%u original_before_capture=1 late_only_forwards=1 slot_preserved=1\n",scenario);
    }
    *context_global=saved_context;*after_slot=saved_after;*after_arg=saved_arg;
    int rect_state_rc=rect_state_contract(base,post);
    if(rect_state_rc){printf("NATIVE_RECT_STATE_FAIL %d\n",rect_state_rc);return 41;}
    if(rect_contract(base,post))return 40;
    if(rect_backend_contract(base))return 42;
    printf("NATIVE_FRAME_CALLBACK_OK 26 native_setters native_order native_scope passive_observer event_handoff retirement_interleaving gain_handoff present_chain present_handoff simulated_state_application\n");
    return 0;
}

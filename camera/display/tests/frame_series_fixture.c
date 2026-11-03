#include <assert.h>
#include <stdio.h>
#include <pthread.h>
#include <sched.h>
#include "../module/frame_series.h"
static struct frame_series state;
static series_fn slot;
static unsigned draws,forwards,entered,leave,blocking,recurse;
static void original(void){__atomic_add_fetch(&forwards,1,__ATOMIC_SEQ_CST);}
static void wrapper(void){series_enter(&state);}
static void foreign(void){}
static void draw(void){
    draws++;
    if(recurse){recurse=0;wrapper();}
    if(blocking){
        __atomic_store_n(&entered,1,__ATOMIC_RELEASE);
        while(!__atomic_load_n(&leave,__ATOMIC_ACQUIRE))sched_yield();
    }
}
static void reset(void){state=(struct frame_series){0};slot=original;draws=forwards=entered=leave=blocking=recurse=0;}
static void *run(void *unused){(void)unused;wrapper();return 0;}
int main(void){
    reset();assert(!series_prepare(&state,&slot,original,wrapper,draw));
    for(int i=0;i<100;i++)slot();
    assert(draws==100&&forwards==100&&slot==wrapper);
    assert(!series_stop(&state)&&slot==original);wrapper();
    assert(draws==100&&forwards==101);assert(!series_stop(&state));
    reset();assert(!series_prepare(&state,&slot,original,wrapper,draw));recurse=1;slot();
    assert(draws==1&&forwards==2);assert(!series_stop(&state));
    reset();assert(!series_prepare(&state,&slot,original,wrapper,draw));slot=foreign;
    assert(series_stop(&state)==-2&&slot==foreign);wrapper();assert(!draws&&forwards==1);
    reset();slot=foreign;assert(series_prepare(&state,&slot,original,wrapper,draw)==-2);
    wrapper();assert(!draws&&forwards==1&&slot==foreign);
    reset();assert(!series_prepare(&state,&slot,original,wrapper,draw));blocking=1;
    pthread_t t;assert(!pthread_create(&t,0,run,0));
    while(!__atomic_load_n(&entered,__ATOMIC_ACQUIRE))sched_yield();
    assert(series_stop(&state)==1&&slot==original);
    __atomic_store_n(&leave,1,__ATOMIC_RELEASE);assert(!pthread_join(t,0));
    assert(!series_stop(&state));wrapper();assert(draws==1&&forwards==2);
    /* Sleep and inactive are independent, idempotent gates. No slot changes
     * are needed for temporary pauses, including a late-fetched wrapper. */
    reset();assert(series_pause(&state,SERIES_SLEEP)==-1);
    assert(!series_prepare(&state,&slot,original,wrapper,draw));
    assert(series_pause(&state,0)==-1&&series_resume(&state,4)==-1);
    for(unsigned order=0;order<2;order++){
        unsigned first=order?SERIES_INACTIVE:SERIES_SLEEP;
        unsigned second=order?SERIES_SLEEP:SERIES_INACTIVE;
        unsigned before=draws,forwarded=forwards;
        assert(!series_pause(&state,first));assert(!series_pause(&state,first));
        assert(!series_pause(&state,second));wrapper();
        assert(slot==wrapper&&draws==before&&forwards==forwarded+1);
        assert(!series_resume(&state,first));wrapper();assert(draws==before);
        assert(!series_resume(&state,second));wrapper();assert(draws==before+1);
    }
    assert(!series_pause(&state,SERIES_SLEEP));unsigned before=draws;
    assert(!series_stop(&state));assert(!series_resume(&state,SERIES_SLEEP));
    wrapper();assert(draws==before&&slot==original);
    /* A pause reports in-flight work, prevents new custom work and lets the
     * old draw drain. Resume never revives a permanently stopped callback. */
    reset();assert(!series_prepare(&state,&slot,original,wrapper,draw));blocking=1;
    assert(!pthread_create(&t,0,run,0));
    while(!__atomic_load_n(&entered,__ATOMIC_ACQUIRE))sched_yield();
    assert(series_pause(&state,SERIES_SLEEP)==1);wrapper();assert(draws==1);
    __atomic_store_n(&leave,1,__ATOMIC_RELEASE);assert(!pthread_join(t,0));
    assert(!series_pause(&state,SERIES_SLEEP));wrapper();assert(draws==1);
    assert(!series_resume(&state,SERIES_SLEEP));blocking=0;wrapper();assert(draws==2);
    assert(!series_stop(&state));
    puts("FRAME_SERIES_OK repeated reentrant cancelled foreign late_forward drain lifecycle_two_gates paused_inflight");
}

/* Host-only observer tests. Deliberately stop/reenter while sampling. */
#include <assert.h>
#include <stdio.h>
#include <pthread.h>
#include <string.h>
#include "../module/frame_observer.h"
static struct frame_observer observer;
static unsigned sec=100,nsec,clock_calls,tid_calls,mode;
static unsigned blocked,unblock;
static int frame_observer_clock(unsigned *s,unsigned *ns) {
    clock_calls++;*s=sec;*ns=nsec;
    if(mode==1)frame_observer_tick(&observer);
    if(mode==2)frame_observer_stop(&observer);
    if(mode==3)return -1;
    if(mode==4) {
        __atomic_store_n(&blocked,1,__ATOMIC_RELEASE);
        while(!__atomic_load_n(&unblock,__ATOMIC_ACQUIRE)){}
    }
    return 0;
}
static int frame_observer_tid(unsigned *tid){tid_calls++;*tid=42;return mode==5?-1:0;}
static void reset(void){memset(&observer,0,sizeof observer);sec=100;nsec=mode=clock_calls=tid_calls=0;}
static void *tick_thread(void *unused){(void)unused;frame_observer_tick(&observer);return 0;}
int main(void) {
    struct frame_observer copy;
    reset();frame_observer_tick(&observer);assert(!clock_calls&&!tid_calls);
    assert(frame_observer_arm(&observer,0)==-1&&frame_observer_arm(&observer,11)==-1);
    assert(frame_observer_arm(&observer,10)==0);
    for(unsigned i=0;i<32;i++){nsec=i*1000000;frame_observer_tick(&observer);}
    assert(observer.count==32&&fo_load(&observer.phase)==FO_FULL);
    assert(frame_observer_snapshot(&observer,&copy)==0&&copy.samples[31].nsec==31000000);
    unsigned calls=clock_calls;
    for(unsigned i=0;i<1000;i++)frame_observer_tick(&observer);
    assert(clock_calls==calls&&tid_calls==32); /* full => zero sampler calls */
    assert(frame_observer_arm(&observer,10)==-1);
    reset();assert(!frame_observer_arm(&observer,10));mode=1;
    frame_observer_tick(&observer);assert(observer.count==1&&clock_calls==2);
    reset();assert(!frame_observer_arm(&observer,10));mode=2;
    frame_observer_tick(&observer);assert(!observer.count&&fo_load(&observer.phase)==FO_STOPPED);
    reset();assert(!frame_observer_arm(&observer,10));mode=3;
    frame_observer_tick(&observer);assert(!observer.count&&fo_load(&observer.phase)==FO_FAILED);
    reset();assert(!frame_observer_arm(&observer,10));mode=5;
    frame_observer_tick(&observer);assert(!observer.count&&fo_load(&observer.phase)==FO_FAILED);
    reset();assert(!frame_observer_arm(&observer,10));sec=110;
    frame_observer_tick(&observer);assert(!observer.count&&fo_load(&observer.phase)==FO_EXPIRED);
    reset();assert(!frame_observer_arm(&observer,10));sec=99;
    frame_observer_tick(&observer);assert(!observer.count&&fo_load(&observer.phase)==FO_FAILED);
    reset();assert(!frame_observer_arm(&observer,10));nsec=1000000000;
    frame_observer_tick(&observer);assert(!observer.count&&fo_load(&observer.phase)==FO_FAILED);
    reset();assert(!frame_observer_arm(&observer,10));nsec=100;frame_observer_tick(&observer);
    nsec=99;frame_observer_tick(&observer);assert(observer.count==1&&fo_load(&observer.phase)==FO_FAILED);
    reset();assert(!frame_observer_arm(&observer,10));mode=4;
    pthread_t thread;assert(!pthread_create(&thread,0,tick_thread,0));
    while(!__atomic_load_n(&blocked,__ATOMIC_ACQUIRE)){}
    assert(frame_observer_snapshot(&observer,&copy)==-1);
    frame_observer_stop(&observer);frame_observer_tick(&observer);
    __atomic_store_n(&unblock,1,__ATOMIC_RELEASE);
    assert(!pthread_join(thread,0));
    assert(!observer.count&&fo_load(&observer.phase)==FO_STOPPED&&!fo_load(&observer.busy));
    calls=clock_calls;frame_observer_tick(&observer);assert(clock_calls==calls);
    assert(frame_observer_arm(&observer,10)==-1);
    printf("FRAME_OBSERVER_OK bounded_samples reentry stop_inflight late_call errors expiry snapshot\n");
    return 0;
}

#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include "../module/event_handoff.h"
static struct event_handoff handoff;
static event_handler_fn slot;
static unsigned forwarded,captured,ready,go;
static int payload;
static void original(void *p){assert(p==&payload);__atomic_fetch_add(&forwarded,1,__ATOMIC_RELAXED);}
static void foreign(void *p){(void)p;}
static void capture(void) {
    assert(__atomic_load_n(&slot,__ATOMIC_ACQUIRE)==original);
    __atomic_fetch_add(&captured,1,__ATOMIC_RELAXED);
}
static void wrapper(void *p){event_handoff_enter(&handoff,p);}
static void reset(void){memset(&handoff,0,sizeof handoff);slot=original;forwarded=captured=ready=go=0;}
static void *runner(void *unused) {
    (void)unused;
    event_handler_fn fetched=__atomic_load_n(&slot,__ATOMIC_ACQUIRE);
    __atomic_fetch_add(&ready,1,__ATOMIC_RELEASE);
    while(!__atomic_load_n(&go,__ATOMIC_ACQUIRE)){}
    fetched(&payload);return 0;
}
int main(void) {
    reset();assert(event_handoff_restore(&handoff)==-1);
    assert(event_handoff_prepare(&handoff,&slot,0,wrapper,capture)==-1);
    assert(event_handoff_prepare(&handoff,&slot,original,original,capture)==-1);
    assert(!event_handoff_prepare(&handoff,&slot,original,wrapper,capture));
    pthread_t threads[2];
    for(unsigned i=0;i<2;i++)assert(!pthread_create(&threads[i],0,runner,0));
    while(__atomic_load_n(&ready,__ATOMIC_ACQUIRE)!=2){}
    __atomic_store_n(&go,1,__ATOMIC_RELEASE);
    for(unsigned i=0;i<2;i++)assert(!pthread_join(threads[i],0));
    assert(forwarded==2&&captured==1&&slot==original);
    assert(!event_handoff_restore(&handoff));
    assert(event_handoff_prepare(&handoff,&slot,original,wrapper,capture)==-1);
    reset();assert(!event_handoff_prepare(&handoff,&slot,original,wrapper,capture));
    event_handler_fn fetched=slot;
    assert(!event_handoff_restore(&handoff));fetched(&payload);
    assert(forwarded==1&&!captured&&slot==original);
    reset();assert(!event_handoff_prepare(&handoff,&slot,original,wrapper,capture));
    fetched=slot;slot=foreign;
    assert(event_handoff_restore(&handoff)==-2);fetched(&payload);
    assert(slot==foreign&&forwarded==1&&!captured);
    reset();slot=foreign;
    assert(event_handoff_prepare(&handoff,&slot,original,wrapper,capture)==-2);
    assert(slot==foreign);
    puts("EVENT_HANDOFF_OK concurrent_fetches restore_before_capture late_cancel foreign_preserved");
    return 0;
}

/* Bounded passive post-draw observation core; no hook registration/removal.
 * The caller retains this storage and callback code for every possible late
 * invocation. stop() stops recording; it does NOT prove dispatch quiescence.
 * One-shot arm, non-blocking try-lock, no allocation, logging or graphics.
 * Platform samplers below must be bounded and may not call the UI backend. */
#ifndef A7C_FRAME_OBSERVER_H
#define A7C_FRAME_OBSERVER_H
typedef unsigned int FO_U;
#define FO_SAMPLES 32U
enum {FO_IDLE,FO_ARMED,FO_FULL,FO_STOPPED,FO_FAILED,FO_EXPIRED};
struct frame_sample {FO_U sec,nsec,tid;};
struct frame_observer {
    FO_U phase,busy,count;
    FO_U start_sec,start_nsec,window_sec;
    struct frame_sample samples[FO_SAMPLES];
};
static int frame_observer_clock(FO_U *sec,FO_U *nsec);
static int frame_observer_tid(FO_U *tid);
static FO_U fo_load(FO_U *p){return __atomic_load_n(p,__ATOMIC_ACQUIRE);}
static void fo_store(FO_U *p,FO_U v){__atomic_store_n(p,v,__ATOMIC_RELEASE);}
static int fo_lock(struct frame_observer *o) {
    FO_U zero=0;
    return __atomic_compare_exchange_n(&o->busy,&zero,1,0,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);
}
static void fo_finish(struct frame_observer *o,FO_U phase) {
    FO_U expected=FO_ARMED;
    /* A concurrent stop must not be undone by an in-flight callback. */
    __atomic_compare_exchange_n(&o->phase,&expected,phase,0,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
}
static int frame_observer_arm(struct frame_observer *o,FO_U seconds) {
    if(!seconds||seconds>10||!fo_lock(o))return -1;
    int rc=-1;
    if(fo_load(&o->phase)==FO_IDLE&&o->count==0) {
        FO_U sec,nsec;
        if(!frame_observer_clock(&sec,&nsec)&&nsec<1000000000U) {
            o->start_sec=sec;o->start_nsec=nsec;o->window_sec=seconds;
            FO_U expected=FO_IDLE;
            rc=__atomic_compare_exchange_n(&o->phase,&expected,FO_ARMED,0,
                                           __ATOMIC_RELEASE,__ATOMIC_RELAXED)?0:-1;
        }
    }
    fo_store(&o->busy,0);return rc;
}
static void frame_observer_stop(struct frame_observer *o) {
    /* No wait in any UI callback. Storage/code lifetime is a separate concern. */
    fo_store(&o->phase,FO_STOPPED);
}
static void frame_observer_tick(struct frame_observer *o) {
    if(fo_load(&o->phase)!=FO_ARMED||!fo_lock(o))return;
    if(fo_load(&o->phase)!=FO_ARMED)goto done;
    FO_U sec,nsec,tid;
    if(frame_observer_clock(&sec,&nsec)||nsec>=1000000000U||
       sec<o->start_sec||(sec==o->start_sec&&nsec<o->start_nsec)) {
        fo_finish(o,FO_FAILED);goto done;
    }
    FO_U elapsed=sec-o->start_sec;
    if(elapsed>o->window_sec||(elapsed==o->window_sec&&nsec>=o->start_nsec)) {
        fo_finish(o,FO_EXPIRED);goto done;
    }
    if(o->count) {
        struct frame_sample *last=&o->samples[o->count-1];
        if(sec<last->sec||(sec==last->sec&&nsec<last->nsec)) {
            fo_finish(o,FO_FAILED);goto done;
        }
    }
    if(frame_observer_tid(&tid)||!tid){fo_finish(o,FO_FAILED);goto done;}
    if(fo_load(&o->phase)==FO_ARMED&&o->count<FO_SAMPLES) {
        o->samples[o->count++]=(struct frame_sample){sec,nsec,tid};
        if(o->count==FO_SAMPLES)fo_finish(o,FO_FULL);
    }
done:
    fo_store(&o->busy,0);
}
/* A snapshot can fail immediately while a callback is sampling. It does not
 * return a partial sample and does not imply the native slot is detached. */
static int frame_observer_snapshot(struct frame_observer *o,struct frame_observer *out) {
    if(!fo_lock(o))return -1;
    out->phase=fo_load(&o->phase);out->busy=0;out->count=o->count;
    out->start_sec=o->start_sec;out->start_nsec=o->start_nsec;out->window_sec=o->window_sec;
    for(FO_U i=0;i<o->count;i++)out->samples[i]=o->samples[i];
    fo_store(&o->busy,0);return 0;
}
#endif

/* One-shot single-argument callback handoff; initially internal+0x14 Event*.
 * Both original and replacement are non-null functions with the same ABI.
 * Restore the original BEFORE capture/delegation; stale fetched wrappers may
 * still arrive, so retain this code and state until lifetime is proven safe.
 * This does not install/remove a GraphicsEngine callback or prove its thread.
 */
#ifndef A7C_EVENT_HANDOFF_H
#define A7C_EVENT_HANDOFF_H
typedef void (*event_handler_fn)(void *);
struct event_handoff {
    event_handler_fn *slot,original,self;
    void (*capture)(void);
    unsigned initialized;
};
/* Setup is single-controller and one-shot, prior to any wrapper publication.
 * The live controller must pin object identity, code hashes and exact ABI. */
static int event_handoff_prepare(struct event_handoff *h,event_handler_fn *slot,
                                event_handler_fn original,event_handler_fn self,
                                void (*capture)(void)) {
    if(h->initialized||!slot||!original||!self||self==original||!capture)return -1;
    h->slot=slot;h->original=original;h->self=self;h->capture=capture;
    h->initialized=1;
    event_handler_fn expected=original;
    return __atomic_compare_exchange_n(slot,&expected,self,0,__ATOMIC_ACQ_REL,
                                       __ATOMIC_ACQUIRE)?0:-2;
}
static int event_handoff_restore(struct event_handoff *h) {
    if(!h->initialized)return -1;
    event_handler_fn expected=h->self;
    if(__atomic_compare_exchange_n(h->slot,&expected,h->original,0,__ATOMIC_ACQ_REL,
                                  __ATOMIC_ACQUIRE))return 0;
    return expected==h->original?0:-2; /* never overwrite a third party */
}
static inline void event_handoff_enter(struct event_handoff *h,void *event) {
    event_handler_fn expected=h->self;
    if(__atomic_compare_exchange_n(h->slot,&expected,h->original,0,__ATOMIC_ACQ_REL,
                                  __ATOMIC_ACQUIRE))h->capture();
    /* Each invocation owes its own original call, even a late invocation that
     * lost the restoration race. Never consume, modify or free the event. */
    h->original(event);
}
/* For a native post-present callback with the same void(void*) ABI: preserve
 * its original completion work BEFORE observing/compositing. Restoration is
 * still before either call; an already committed sample may finish after an
 * external restore, so code and data must remain mapped exactly as above. */
static inline void event_handoff_enter_after(struct event_handoff *h,void *arg) {
    event_handler_fn expected=h->self;
    unsigned won=__atomic_compare_exchange_n(h->slot,&expected,h->original,0,
                                             __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
    h->original(arg);
    if(won)h->capture();
}
#endif

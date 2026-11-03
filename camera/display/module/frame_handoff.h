/* Candidate for the no-argument GraphicsSystem gain callback. The native
 * caller reads this function pointer once; original must remain non-null.
 * This distinct ABI must not use event_handoff's Event* function type.
 * Restore before sampling, forward every call, retain immutable code/state.
 * No GraphicsEngine slot, enabled flag, font, driver or allocation changes.
 */
#ifndef A7C_FRAME_HANDOFF_H
#define A7C_FRAME_HANDOFF_H
typedef void (*frame_handler_fn)(void);
struct frame_handoff {
    frame_handler_fn *slot,original,self,capture;
    unsigned initialized;
};
static int frame_handoff_prepare(struct frame_handoff *h,frame_handler_fn *slot,
                                frame_handler_fn original,frame_handler_fn self,
                                frame_handler_fn capture) {
    if(h->initialized||!slot||!original||!self||self==original||!capture)return -1;
    h->slot=slot;h->original=original;h->self=self;h->capture=capture;
    h->initialized=1;
    frame_handler_fn expected=original;
    return __atomic_compare_exchange_n(slot,&expected,self,0,__ATOMIC_ACQ_REL,
                                       __ATOMIC_ACQUIRE)?0:-2;
}
static int frame_handoff_restore(struct frame_handoff *h) {
    if(!h->initialized)return -1;
    frame_handler_fn expected=h->self;
    if(__atomic_compare_exchange_n(h->slot,&expected,h->original,0,__ATOMIC_ACQ_REL,
                                  __ATOMIC_ACQUIRE))return 0;
    return expected==h->original?0:-2;
}
static void frame_handoff_enter(struct frame_handoff *h) {
    frame_handler_fn expected=h->self;
    if(__atomic_compare_exchange_n(h->slot,&expected,h->original,0,__ATOMIC_ACQ_REL,
                                  __ATOMIC_ACQUIRE))h->capture();
    h->original();
}
#endif

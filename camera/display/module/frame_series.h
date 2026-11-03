/* Bounded trial handoff. All native calls are forwarded. Stop gates new draw
 * work before restoring the slot; caller drains busy before native redraw.
 * Immutable code/state must remain mapped for late-fetched wrappers. */
#ifndef A7C_FRAME_SERIES_H
#define A7C_FRAME_SERIES_H
typedef void (*series_fn)(void);
enum { SERIES_SLEEP=1, SERIES_INACTIVE=2 };
struct frame_series { series_fn *slot,original,self,draw; unsigned initialized,active,busy,paused; };
static int series_prepare(struct frame_series *s,series_fn *slot,series_fn original,
                          series_fn self,series_fn draw){
    if(s->initialized||!slot||!original||!self||self==original||!draw)return -1;
    s->slot=slot;s->original=original;s->self=self;s->draw=draw;s->initialized=1;
    __atomic_store_n(&s->paused,0,__ATOMIC_RELEASE);
    __atomic_store_n(&s->active,1,__ATOMIC_RELEASE);
    series_fn expected=original;
    if(__atomic_compare_exchange_n(slot,&expected,self,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))return 0;
    __atomic_store_n(&s->active,0,__ATOMIC_RELEASE);return -2;
}
static int series_stop(struct frame_series *s){
    if(!s->initialized)return -1;
    __atomic_store_n(&s->active,0,__ATOMIC_RELEASE);
    series_fn expected=s->self;
    if(!__atomic_compare_exchange_n(s->slot,&expected,s->original,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)&&
       expected!=s->original)return -2;
    return __atomic_load_n(&s->busy,__ATOMIC_ACQUIRE)?1:0;
}
/* Lifecycle notifications can overlap. Keep the wrapper installed but forward
 * only Sony's function while either reason remains. This avoids changing the
 * callback slot during power transitions, and resume cannot undo a final stop.
 * A caller that tears down graphics must wait for a returned busy=1 to drain. */
static inline int series_pause(struct frame_series *s,unsigned reason){
    if(!s->initialized||!reason||(reason&~3U))return -1;
    __atomic_fetch_or(&s->paused,reason,__ATOMIC_ACQ_REL);
    return __atomic_load_n(&s->busy,__ATOMIC_ACQUIRE)?1:0;
}
static inline int series_resume(struct frame_series *s,unsigned reason){
    if(!s->initialized||!reason||(reason&~3U))return -1;
    __atomic_fetch_and(&s->paused,~reason,__ATOMIC_ACQ_REL);
    return 0;
}
static void series_enter(struct frame_series *s){
    unsigned zero=0;
    if(__atomic_compare_exchange_n(&s->busy,&zero,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)){
        if(__atomic_load_n(&s->active,__ATOMIC_ACQUIRE)&&
           !__atomic_load_n(&s->paused,__ATOMIC_ACQUIRE)&&
           __atomic_load_n(s->slot,__ATOMIC_ACQUIRE)==s->self)s->draw();
        __atomic_store_n(&s->busy,0,__ATOMIC_RELEASE);
    }
    s->original();
}
#endif

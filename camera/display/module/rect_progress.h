/* Atomic mailbox: sequence in high 24 bits, enabled bit7, percent low7.
 * External consumer owns request identity/files; drawing thread does no I/O.
 * Zero before first command waits briefly; zero after a command stops.
 * Stale heartbeat and deadline retire the hook without drawing again. */
#ifndef A7C_RECT_PROGRESS_H
#define A7C_RECT_PROGRESS_H
struct rect_progress { unsigned initialized,seen,word,renewed,started,percent; };
static int rect_progress_step(struct rect_progress *s,unsigned word,unsigned now,unsigned *percent){
    if(!s->initialized){s->initialized=1;s->started=s->renewed=now;}
    if(now-s->started>=60000U)return -3;
    if(!word)return s->seen?-1:now-s->started>=3000U?-3:0;
    if(!(word&128U)||(word&127U)>99U||!(word>>8))return -2;
    if(!s->seen||word!=s->word){s->word=word;s->renewed=now;s->seen=1;}
    else if(now-s->renewed>=3000U)return -3;
    unsigned next=word&127U;
    if(next>s->percent)s->percent=next; /* native additive fill never shrinks */
    *percent=s->percent;return 1;
}
#endif

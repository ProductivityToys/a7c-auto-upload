/* Service-owned indicator, evaluated only on native UI redraws.
 * Idle=100, FTP error=102, active transfer=0..99. No background thread or timer.
 * Caller caches kill(owner,0) for one second while the UI is already awake.
 */
#ifndef A7C_RECT_SERVICE_H
#define A7C_RECT_SERVICE_H
struct rect_service { unsigned started,initialized,owner,word,renewed,percent,mode; };
static int rect_service_step(struct rect_service *s,unsigned owner,int alive,unsigned word,unsigned health,unsigned now,unsigned *mode){
 if(!s->initialized){s->initialized=1;s->started=now;s->mode=100;}
 if(owner>0x7fffffffU||owner==1)return -1;
 if(!owner||!alive){s->owner=s->word=s->percent=0;s->mode=101;*mode=101;return 0;}
 if(s->owner!=owner){s->word=s->percent=0;s->mode=100;}
 s->owner=owner;
 if(!word){s->word=0;s->percent=0;s->mode=100;}
 else {
  if(!(word&128U)||(word&127U)>99U||!(word>>8))return -1;
  if(word!=s->word){
   if(s->mode>=100)s->percent=0;
   s->word=word;s->renewed=now;
   if((word&127U)>s->percent)s->percent=word&127U;
  }
  s->mode=now-s->renewed>=3000U?100:s->percent;
 }
 if(s->mode==100&&health==2)s->mode=102; /* FTP unavailable, persistent idle mark. */
 *mode=s->mode;
#ifdef A7C_SERVICE_NO_IDLE
 /* Experimental ablation only: same mailbox/owner semantics, no idle GPU work. */
 return s->mode>=100?0:1;
#else
 return 1;
#endif
}
#endif

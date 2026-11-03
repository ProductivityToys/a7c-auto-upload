#include <assert.h>
#include <stdio.h>
#include "../module/rect_service.h"
#ifdef A7C_SERVICE_NO_IDLE
#define IDLE_RESULT 0
#else
#define IDLE_RESULT 1
#endif
int main(void){
 struct rect_service s={0};unsigned mode=999;
 assert(!rect_service_step(&s,0,0,0,1,10,&mode));
 assert(rect_service_step(&s,3425,1,0,1,100,&mode)==IDLE_RESULT&&mode==100);
 for(unsigned now=1000;now<1000000;now+=1000)assert(rect_service_step(&s,3425,1,0,1,now,&mode)==IDLE_RESULT&&mode==100);
 assert(rect_service_step(&s,3425,1,256|128|20,1,1000000,&mode)==1&&mode==20);
 assert(rect_service_step(&s,3425,1,512|128|99,1,1001000,&mode)==1&&mode==99);
 assert(rect_service_step(&s,3425,1,0,1,1001500,&mode)==IDLE_RESULT&&mode==100);
 assert(rect_service_step(&s,3425,1,256|128|4,1,1002000,&mode)==1&&mode==4);
 assert(rect_service_step(&s,3425,1,256|128|4,1,1005000,&mode)==IDLE_RESULT&&mode==100);
 assert(rect_service_step(&s,3425,1,512|128|20,1,1005500,&mode)==1&&mode==20);
 assert(rect_service_step(&s,3425,0,0,1,1006000,&mode)==0&&mode==101);
 assert(rect_service_step(&s,3426,1,0,1,1006000,&mode)==IDLE_RESULT&&mode==100);
 assert(rect_service_step(&s,0,0,0,1,1006000,&mode)==0&&mode==101);
 assert(rect_service_step(&s,3427,1,256|128|4,1,1006500,&mode)==1&&mode==4);
 assert(rect_service_step(&s,3427,1,0,2,1007000,&mode)==IDLE_RESULT&&mode==102);
 assert(rect_service_step(&s,3427,1,0,2,1008000,&mode)==IDLE_RESULT&&mode==102);
 assert(rect_service_step(&s,3427,1,512|128|20,2,1009000,&mode)==1&&mode==20);
 assert(rect_service_step(&s,3427,1,0,1,1010000,&mode)==IDLE_RESULT&&mode==100);
 puts("RECT_SERVICE_OK idle_without_poll transfer idle next_task stale_owner_stop");
}

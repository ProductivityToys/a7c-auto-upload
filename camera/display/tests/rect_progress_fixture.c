#include <assert.h>
#include <stdio.h>
#include "../module/rect_progress.h"
int main(void){
 struct rect_progress s={0};unsigned p=100;
 assert(!rect_progress_step(&s,0,100,&p));assert(!rect_progress_step(&s,0,3099,&p));
 assert(rect_progress_step(&s,0,3100,&p)==-3);
 s=(struct rect_progress){0};assert(rect_progress_step(&s,256|128|0,100,&p)==1&&p==0);
 assert(rect_progress_step(&s,512|128|42,1100,&p)==1&&p==42);
 assert(rect_progress_step(&s,768|128|20,2100,&p)==1&&p==42);
 assert(rect_progress_step(&s,1024|128|99,3100,&p)==1&&p==99);
 assert(rect_progress_step(&s,1024|128|99,6099,&p)==1);
 assert(rect_progress_step(&s,1024|128|99,6100,&p)==-3);
 assert(rect_progress_step(&s,0,6100,&p)==-1);
 for(unsigned w=100;w<128;w++){s=(struct rect_progress){0};assert(rect_progress_step(&s,256|128|w,100,&p)==-2);}
 s=(struct rect_progress){0};assert(rect_progress_step(&s,128|42,100,&p)==-2);
 s=(struct rect_progress){0};assert(rect_progress_step(&s,256|42,100,&p)==-2);
 s=(struct rect_progress){0};assert(rect_progress_step(&s,256|128|42,0xfffffff0U,&p)==1);
 assert(rect_progress_step(&s,512|128|43,0x100U,&p)==1&&p==43);
 s=(struct rect_progress){0};assert(rect_progress_step(&s,256|128|1,100,&p)==1);
 assert(rect_progress_step(&s,512|128|99,60100,&p)==-3);
 puts("RECT_PROGRESS_OK pending monotonic stale stop malformed wrap deadline");
}

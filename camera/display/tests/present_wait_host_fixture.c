/* Passive wait must never fork/query the UI; only marker reads and polling. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned U;
#include "../module/event_state.h"
static unsigned scenario,polls;
static int rd(U address,void *out,unsigned size) {
    struct event_marker m={0};
    if(scenario==4)return -1;
    if(scenario!=3&&(scenario!=1||polls==2)) {
        m.captured=1;m.tid=scenario==5?0:403;m.capture_rc=scenario==2?-3:0;
    }
    if(address==0x1000&&size==sizeof m)memcpy(out,&m,size);
    else if(address==0x102c&&size==4)memcpy(out,&m.captured,size);
    else return -1;
    return 0;
}
static int poll(void *p,unsigned n,int delay){assert(!p&&!n&&delay==25);polls++;return 0;}
#define PRESENT_TRIAL
#include "../module/event_control.h"
int main(void) {
    event_marker_address=0x1000;
    for(scenario=0;scenario<6;scenario++) {
        polls=0;
        assert(event_wait(162)==(scenario<2?0:-1));
        assert(polls==(scenario==1?2:scenario==3?160:0));
    }
    puts("PRESENT_WAIT_OK 6 passive_no_query");return 0;
}

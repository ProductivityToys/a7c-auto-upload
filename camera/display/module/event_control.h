/* External bounded controller, never run in an im callback. */
#include "event_state.h"
extern int execv(const char *,char *const *);
static U event_marker_address;
static int event_read(struct event_marker *out) {
    U captured;
    if(!event_marker_address||rd(event_marker_address,out,sizeof *out)||
       rd(event_marker_address+44,&captured,4)||captured!=out->captured)return -1;
    return 0;
}
#ifdef RECT_UPLOAD_TRIAL
#include "rect_upload_control.h"
#endif
#ifdef RECT_SERVICE_TRIAL
static int rect_service_setup(int pid);
#endif
static int event_wait(int pid) {
#ifdef RECT_SERVICE_TRIAL
    return rect_service_setup(pid);
#elif defined(RECT_UPLOAD_TRIAL)
    return rect_upload_wait(pid);
#elif defined(RECT_SERIES_TRIAL)
    (void)pid;
    for(U i=0;i<480;i++) {
        struct event_marker m; U series[5];
        if(event_read(&m)||rd(event_marker_address+sizeof m+12,series,sizeof series))return -1;
        if(series[3]) {
            printf("SERIES_WAIT frames=%u changes=%u percent=%u stopped=%u rc=%d query_sent=0\n",
                   series[0],series[1],series[2],series[3],m.capture_rc);fflush(0);
            return series[3]==1&&series[0]&&series[1]==3&&series[2]==80&&!m.capture_rc?0:-1;
        }
        poll(0,0,25);
    }
    printf("SERIES_WAIT timeout=1\n");fflush(0);return -1;
#elif defined(PRESENT_TRIAL) || defined(RECT_TRIAL)
    /* A UI query can itself cause another frame and erase the one-shot glyph.
     * Observe the natural present callback without injecting testcmd activity. */
    (void)pid;
    for(U i=0;i<160;i++) {
        struct event_marker m;
        if(event_read(&m))return -1;
        if(m.captured==1) {
            printf("PRESENT_WAIT captured=1 rc=%d tid=%u query_sent=0\n",m.capture_rc,m.tid);fflush(0);
            return !m.capture_rc&&m.tid?0:-1;
        }
        poll(0,0,25);
    }
    printf("PRESENT_WAIT captured=0 query_sent=0 timeout=1\n");fflush(0);
    return -1;
#else
    int child=fork();if(child<0)return -1;
    if(!child) {
        if(guard_writer>=0)close(guard_writer);
        alarm(5);
        char *const args[]={"/usr/bin/testcmd.elf","--sync","0x0083014b","5","1","1","1",0};
        execv(args[0],args);_exit(127);
    }
    int done=0,status=0,seen=0;
    struct event_marker m;
    for(U i=0;i<160;i++) {
        if(!done){int w=waitpid(child,&status,1);if(w==child)done=1;else if(w<0)break;}
        if(event_read(&m))break;
        if(m.captured==1&&!m.capture_rc&&m.tid)seen=1;
        if(seen&&done)break;
        poll(0,0,25);
    }
    if(!done){kill(child,15);usleep(100000);if(waitpid(child,&status,1)==0){kill(child,9);waitpid(child,&status,0);}}
    printf("EVENT_WAIT captured=%d query_done=%d query_status=%d\n",seen,done,status);fflush(0);
    if(seen) {
        char path[80],name[80];snprintf(path,sizeof path,"/proc/%d/task/%u/comm",pid,m.tid);
        int f=open(path,0);int n=f<0?-1:read(f,name,sizeof name-1);if(f>=0)close(f);
        if(n>0){name[n]=0;printf("EVENT_THREAD tid=%u name=%s",m.tid,name);}
    }
    return seen&&done&&!status?0:-1;
#endif
}

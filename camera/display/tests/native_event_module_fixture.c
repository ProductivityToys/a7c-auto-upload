/* Same built DSO against native event dispatch in isolated ARM userspace.
 * Fake manager/internal objects; never camera memory, UI, GPU or network. */
#include "../module/event_state.h"
typedef unsigned U;
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern int printf(const char *,...),fork(void),waitpid(int,int *,int);
extern void _exit(int);
extern unsigned alarm(unsigned);
static U view[16],internal[24],event[8];
static void foreign(void *p){(void)p;}
int main(void) {
    alarm(15);
    void *native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    U base=(U)dlsym(native,"TextRM_loadFont")-0x57d271;
    void *module=dlopen("/trial/marker.so",2);if(!module)return 2;
    int (*init)(void)=dlsym(module,"IM_SAMPLE_SO_init");
    int (*finish)(void)=dlsym(module,"IM_SAMPLE_SO_exit");
    struct event_marker *m=dlsym(module,"a7c_native_marker");
    if(!init||!finish||!m)return 3;
    U previous=*(U *)(base+0x1488fdc);
    view[0x14/4]=(U)internal;internal[0x14/4]=base+0x3ef545;
    *(U *)(base+0x1488fdc)=(U)view;
    void (*dispatch)(void *,void *)=(void *)(base+0x89f58d);
    for(U scenario=0;scenario<3;scenario++) {
        int child=fork();if(child<0)return 4;
        if(!child) {
            int error=0;
            if(init()||m->init!=1||m->prepare_rc||!m->init_tid)_exit(10);
            void (*fetched)(void *)=(void *)internal[0x14/4];
            if((U)fetched==base+0x3ef545)_exit(11);
            if(scenario==0) {
                dispatch(internal,event);
                if(m->captured!=1||m->capture_rc||m->tid!=m->init_tid||
                   internal[0x14/4]!=base+0x3ef545)_exit(12);
                fetched(event);
                error=finish()||m->exit!=1||m->restore_rc||m->captured!=1;
            } else if(scenario==1) {
                error=finish()||m->restore_rc||internal[0x14/4]!=base+0x3ef545;
                fetched(event);error|=m->captured!=0;
            } else {
                internal[0x14/4]=(U)foreign;
                error=finish()!=-2||m->restore_rc!=-2||internal[0x14/4]!=(U)foreign;
                fetched(event);error|=m->captured!=0||internal[0x14/4]!=(U)foreign;
            }
            _exit(error?13:0);
        }
        int status=0;if(waitpid(child,&status,0)!=child||status)return 20+scenario;
        printf("EVENT_MODULE_CASE scenario=%u ok=1\n",scenario);
    }
    *(U *)(base+0x1488fdc)=previous;
    printf("NATIVE_EVENT_MODULE_OK 3 actual_dso actual_event_dispatch fake_manager no_camera\n");
    return 0;
}

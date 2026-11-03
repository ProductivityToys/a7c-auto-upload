/* Actual candidate DSO and native gain dispatcher in isolated ARM userspace.
 * Use the fixed lab BSS table; intercept original gain after module validation
 * so no GPU/driver operation can run. No camera or network access. */
#include "../module/event_state.h"
typedef unsigned U;
typedef unsigned short H;
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern int printf(const char *,...),fork(void),waitpid(int,int *,int);
extern int mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
extern void _exit(int);
extern unsigned alarm(unsigned);
static U forwarded;
static U scope_outer[260],scope_delegate[64];
static void original(void){forwarded++;}
static void foreign(void){}
static int intercept(U address) {
    U page=address&~4095U;
    if(mprotect((void *)page,8192,7))return -1;
    H *code=(void *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *literal=(void *)(address+4);U dest=(U)original;
    for(U i=0;i<4;i++)literal[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5);
}
int main(void) {
    alarm(15);
    void *native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    U base=(U)dlsym(native,"TextRM_loadFont")-0x57d271;
    void *module=dlopen("/trial/marker.so",2);if(!module)return 2;
    int (*init)(void)=dlsym(module,"IM_SAMPLE_SO_init");
    int (*finish)(void)=dlsym(module,"IM_SAMPLE_SO_exit");
    struct event_marker *m=dlsym(module,"a7c_native_marker");
    if(!init||!finish||!m||(m->version!=11&&m->version!=15))return 3;
    U *global=(void *)(base+0x1453914),*table=(void *)(base+0x14539d8);
    void (*dispatch)(void)=(void *)(base+0x66de3d);
    for(U scenario=0;scenario<(m->version==15?11U:5U);scenario++) {
        int child=fork();if(child<0)return 4;
        if(!child) {
            int error=0;U *slot=table+0x5c/4;
            *global=(U)table;*slot=base+0x675279;
            if(scenario==3) {
                *global=0;
                if(init()!=-2||m->prepare_rc!=-2||*slot!=base+0x675279||finish())_exit(14);
                _exit(0);
            }
            if(scenario==4) {
                *slot=(U)foreign;
                if(init()!=-2||m->prepare_rc!=-2||*slot!=(U)foreign||finish()!=-2)_exit(15);
                _exit(0);
            }
            int scope_error=0;
            U *scope=(void *)((unsigned char *)m+sizeof *m);
            if(m->version==15) {
                *(U *)(base+0x1453918)=(U)scope_outer;
                scope_outer[0]=base+0x13b68c0;
                scope_outer[4]=(U)scope_delegate;scope_delegate[0]=base+0x13b6648;
                scope_outer[0x348/4]=1;
                ((unsigned char *)scope_outer)[0x404]=scenario==5?0:1;
                ((unsigned char *)scope_delegate)[0xa4]=scenario==5?0:1;
                *(H *)((unsigned char *)scope_outer+0x326)=scenario==5?0:5;
                scope_outer[0x310/4]=scenario==5?0:20;
                scope_outer[0x31c/4]=scenario==5?0:28;
                if(scenario==7){*(U *)(base+0x1453918)=0;scope_error=-1;}
                if(scenario==8){scope_outer[0]=0;scope_error=-1;}
                if(scenario==9){scope_outer[4]=0;scope_error=-2;}
                if(scenario==10){scope_delegate[0]=0;scope_error=-2;}
            }
            if(init()||m->init!=1||m->prepare_rc||!m->init_tid)_exit(10);
            void (*fetched)(void)=(void *)*slot;
            if((U)fetched==base+0x675279||intercept(base+0x675278))_exit(11);
            if(scenario==0||scenario>=5) {
                dispatch();
                if(m->captured!=1||m->capture_rc!=scope_error||m->tid!=m->init_tid||
                   *slot!=base+0x675279||forwarded!=1)_exit(12);
                if(m->version==15) {
                    if((int)scope[8]!=scope_error)_exit(16);
                    if(!scope_error&&(scope[0]!=(U)scope_outer||scope[1]!=(U)scope_delegate||
                       scope[2]!=(scenario==5?0U:1U)||scope[3]!=1||
                       scope[4]!=(scenario==5?0U:1U)||scope[5]!=(scenario==5?0U:5U)||
                       scope[6]!=(scenario==5?0U:20U)||scope[7]!=(scenario==5?0U:28U)))_exit(17);
                    /* A stale dispatch must forward without overwriting the first snapshot. */
                    scope_outer[0x348/4]=0;
                }
                fetched();
                if(m->version==15&&!scope_error&&scope[3]!=1)_exit(18);
                error=finish()||m->exit!=1||m->restore_rc||m->captured!=1||forwarded!=2;
            } else if(scenario==1) {
                error=finish()||m->restore_rc||*slot!=base+0x675279;
                fetched();error|=m->captured!=0||forwarded!=1;
            } else {
                *slot=(U)foreign;
                error=finish()!=-2||m->restore_rc!=-2||*slot!=(U)foreign;
                fetched();error|=m->captured!=0||*slot!=(U)foreign||forwarded!=1;
            }
            _exit(error?13:0);
        }
        int status=0;if(waitpid(child,&status,0)!=child||status)return 20+scenario;
        printf("GAIN_MODULE_CASE scenario=%u ok=1\n",scenario);
    }
    if(m->version==15)printf("NATIVE_GAIN_SCOPE_OK 11 active_inactive_reject_stale_forward\n");
    printf("NATIVE_GAIN_MODULE_OK 5 actual_dso actual_gain_dispatch intercepted_original no_camera\n");
    return 0;
}

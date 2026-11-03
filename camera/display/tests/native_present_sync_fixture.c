/* Execute Sony's real wait/destroy with synthetic TLS, fence registry and
 * condition-variable boundaries. No EGL context, GPU, device or camera.
 * This checks the ARM 64-bit timeout ABI and retirement after every result. */
#define A7C_PRESENT_SYNC_OFFLINE 1
#include "../module/present_sync.h"
typedef unsigned U;
typedef unsigned short H;
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern int printf(const char *,...),mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
extern unsigned alarm(unsigned);
static U fence[6],tls[32],created,waited,destroyed,flushed,bad;
static int scenario;
static void noop(void *p){(void)p;}
static int initialized(void){return 1;}
static void *thread_state(void){return tls;}
static int registered(void *list,void *sync){(void)list;if(sync!=fence)bad=1;return 1;}
static void removed(void *list,void *sync){(void)list;if(sync!=fence)bad=1;destroyed++;}
static void flush(U thread,void *display,U a,U b){
    (void)display;if(thread!=123||a!=456||b!=789)bad=1;flushed++;
}
static int timed(U cond,U mutex,const U *timeout){
    if(cond!=55||mutex!=44||timeout[0]!=20000000||timeout[1])bad=1;
    waited++;
    if(scenario==0)fence[2]=0x30f2; /* Simulated genuine GPU signal. */
    return scenario==1?4:scenario==2?7:scenario==3?5:0;
}
static int forever(U cond,U mutex){(void)cond;(void)mutex;bad=1;return 7;}
static void *create(U display,U type,const int *attributes){
    if(display!=1||type!=0x30f9||attributes)bad=1;created++;
    return scenario==4?0:fence;
}
static U failed_destroy(U display,void *sync){
    if(display!=1||sync!=fence)bad=1;destroyed++;return 0;
}
static int intercept(U address,void *destination) {
    U page=address&~4095U;if(mprotect((void *)page,8192,7))return -1;
    H *code=(void *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *literal=(void *)(address+4);U dest=(U)destination;
    for(U i=0;i<4;i++)literal[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5);
}
int main(void){
    alarm(10);
    void *native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    U base=(U)dlsym(native,"TextRM_loadFont")-0x57d271;
    if(intercept(base+0x785a70,create)||intercept(base+0x785160,initialized)||
       intercept(base+0x7851b0,thread_state)||intercept(base+0x783c00,registered)||
       intercept(base+0x783c40,removed)||intercept(base+0x781a40,noop)||
       intercept(base+0x781a50,noop)||intercept(base+0x781780,noop)||
       intercept(base+0x781790,noop)||intercept(base+0x781850,timed)||
       intercept(base+0x781840,forever)||intercept(base+0x78d540,flush))return 2;
    *(U *)(base+0x1454c40)=1;*(U *)(base+0x1454b68+0x10)=1;
    tls[0]=123;tls[2]=0x30a0;tls[9]=456;tls[6]=789;
    for(scenario=0;scenario<7;scenario++){
        created=waited=destroyed=flushed=bad=0;
        fence[0]=2;fence[2]=scenario==5?0x30f2:0x30f3;fence[4]=44;fence[5]=55;
        struct present_sync_result r;
        int rc=present_sync_once(base,scenario==6?0:1,&r);
        int expected=scenario==1||scenario==3?1:scenario==2?-4:scenario==4?-2:scenario==6?-1:0;
        U active=scenario!=4&&scenario!=6;
        if(rc!=expected||bad||created!=(scenario==6?0U:1U)||destroyed!=active||
           flushed!=active||waited!=(active&&scenario!=5)||r.created!=active||
           r.destroy_result!=active||fence[0]!=(active?1U:2U)){
            printf("SYNC_FAIL scenario=%d rc=%d bad=%u c=%u w=%u d=%u f=%u refs=%u\n",
                   scenario,rc,bad,created,waited,destroyed,flushed,fence[0]);return 10+scenario;
        }
        if(scenario==3&&(r.wait_result!=0x30f6||r.poll_result!=0x30f5))return 19;
        printf("SYNC_CASE scenario=%d rc=%d wait=%x poll=%x destroy=%u ok=1\n",scenario,rc,r.wait_result,r.poll_result,r.destroy_result);
    }
    if(intercept(base+0x7858e0,failed_destroy))return 20;
    scenario=0;bad=0;struct present_sync_result r;
    if(present_sync_once(base,1,&r)!=-3||bad||r.destroy_result)return 21;
    printf("NATIVE_PRESENT_SYNC_OK 8 actual_wait_destroy finite_arm_timeout no_gpu\n");
    return 0;
}

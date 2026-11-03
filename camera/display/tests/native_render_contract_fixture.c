/* Offline execution of original renderer decisions; stop at the first GL
 * blend operation. No GL context, bitmap allocation, device or pixel writes.
 * Also check original command completion with an injected backend failure. */
typedef unsigned U;
typedef unsigned short H;
extern int printf(const char *,...);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern int mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
extern unsigned alarm(unsigned);
extern int setjmp(void *) __attribute__((returns_twice));
extern void longjmp(void *,int) __attribute__((noreturn));
static U jump[128] __attribute__((aligned(16)));
static U context[128],params[40],command[72];
static volatile U blend_enabled,blend_enum,setups,notified;
static int backend_rc;
static int zero(void){return 0;}
static int setup(void){setups++;return 0;}
static void enable(U value){blend_enum=value;blend_enabled=1;longjmp(jump,1);}
static void disable(U value){blend_enum=value;blend_enabled=0;longjmp(jump,1);}
static int physical(U object,U *out){*out=object==1?0x100000:0x200000;return 0;}
static int backend(U id,U wait,U *p){(void)id;(void)wait;(void)p;return backend_rc;}
static void notify(U *p){notified++;if(p!=command)notified=99;}
static int replace(U address,void *callback) {
    U page=address&~4095U;
    if(mprotect((void *)page,8192,7))return 1;
    H *code=(H *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *literal=(void *)(address+4);U dest=(U)callback;
    for(U i=0;i<4;i++)literal[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5)!=0;
}
int main(void) {
    alarm(10);
    void *native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    U symbol=(U)dlsym(native,"TextRM_loadFont");if(!symbol)return 2;
    U base=symbol-0x57d271;
    if(replace(base+0x7b87d0,zero)||replace(base+0x7d47c0,setup)||
       replace(base+0x7d48d0,setup)||replace(base+0x7bd0d0,enable)||
       replace(base+0x7bd340,disable))return 3;
    int (*render)(U *,U,U *)=(void *)(base+0x7d2091);
    /* DDS mode 1 lowers to +0x44=0, global alpha to +0x3c=255.
     * Source/destination format 1 lowers to format 0. */
    for(volatile U mode=0;mode<3;mode++) {
        for(U i=0;i<40;i++)params[i]=0;
        params[0x3c/4]=mode==2?128:255;
        params[0x44/4]=mode==1?1:0;
        params[0x8c/4]=0x3f800000;
        setups=0;blend_enum=0;blend_enabled=99;
        if(!setjmp(jump)) {render(context,2,params);return 4;}
        printf("NATIVE_BLEND mode=%u enabled=%u enum=%x setup_calls=%u\n",mode,blend_enabled,blend_enum,setups);
        if(blend_enum!=0xbe2||blend_enabled!=(mode!=0)||setups!=2)return 5;
    }
    if(replace(base+0x68ef24,zero)||replace(base+0x68b940,zero)||
       replace(base+0x68b83c,zero)||replace(base+0x68dbf8,physical)||
       replace(base+0x7d1de0,backend)||replace(base+0x68bbe4,notify))return 6;
    int (*execute)(U *)=(void *)(base+0x68bc05);
    const int failures[]={0,-5,-9999};
    for(U i=0;i<3;i++) {
        for(U j=0;j<72;j++)command[j]=0;
        command[0x2c/4]=1;command[0x30/4]=2;
        backend_rc=failures[i];notified=0;
        int rc=execute(command);
        printf("NATIVE_COMPLETION backend=%d returned=%d reported=%d notifications=%u\n",
            backend_rc,rc,(int)command[0x1c/4],notified);
        if(rc||command[0x1c/4]||notified!=1||command[0x20/4]!=2)return 7;
    }
    printf("NATIVE_RENDER_CONTRACT_OK copy_disables_blend backend_errors_masked\n");
    return 0;
}

/* Offline only. Execute original DDS submit wrapper with all display/GRM
 * boundaries intercepted. No bitmap allocation, GPU, driver or camera access.
 * This checks descriptor construction and error propagation, not rendering. */
typedef unsigned U;
typedef unsigned short H;
#define A7C_NATIVE_SUBMIT_OFFLINE 1
#include "../module/native_submit.h"
extern int printf(const char *,...);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern int mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
extern unsigned alarm(unsigned);
static U mode,bad,held,refs,calls,seen[20],source,front;
static H front_rect[4]={0,0,640,480};
static struct {U before[4];H pixels[288*32];U after[4];} blank;
static int source_locked;
static char events[16];
static U count;
static void event(char c) {
    if(count>=15){bad=1;return;}
    events[count++]=c;events[count]=0;
}
static int enter(void){event('L');if(held)bad=1;held=1;return 0;}
static int leave(void){event('U');if(!held)bad=1;held=0;return 0;}
static int acquire(void **out) {
    event('A');if(!held)bad=1;
    if(mode==2)return -7;
    *out=&front;return 0;
}
static int retain(void *p){event('R');if(p!=&front||!held)bad=1;refs++;return 0;}
static int release(void *p){event('F');if(p!=&front||held||refs!=1)bad=1;refs--;return mode==4?-19:0;}
static int rectangle(void *p,H **out){event('Q');if(p!=&front||held)bad=1;*out=front_rect;return mode==3?-18:0;}
static int submit(U a,U b,const U *desc,U callback,U argument) {
    event('S');if(a||b||callback||argument||held||refs!=1)bad=1;
    calls++;for(U i=0;i<20;i++)seen[i]=desc[i];
    return mode==1?-17:0;
}
static int source_lock(void *p,int timeout,void **out) {
    if(p!=&source||timeout!=-1||source_locked)bad=1;
    source_locked=1;*out=blank.pixels;return 0;
}
static int source_unlock(void *p) {
    if(p!=&source||!source_locked)bad=1;
    source_locked=0;return 0;
}
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
    U address=(U)dlsym(native,"TextRM_loadFont");if(!address)return 2;
    U base=address-0x57d271;
    if(replace(base+0x75ccf4,enter)||replace(base+0x75cce4,leave)||
       replace(base+0x75cca4,acquire)||replace(base+0x68dc48,retain)||
       replace(base+0x68dc58,release)||replace(base+0x68db58,rectangle)||
       replace(base+0x68ce02,submit))return 3;
    int (*original)(void *,const H *,const H *)=(void *)(base+0x68d13d);
    const H src[4]={0,0,71,20},dst[4]={500,420,71,20};
    const U expected[20]={(U)&source,0,(20U<<16)|71,(U)&front,
        (420U<<16)|500,(20U<<16)|71,0,(480U<<16)|640,1,255,
        0,0,0,0,0,0x3f800000,0x3f800000,0,0,0};
    for(mode=0;mode<3;mode++) {
        bad=held=refs=calls=count=0;events[0]=0;
        for(U i=0;i<20;i++)seen[i]=0;
        int rc=original(&source,src,dst);
        const char *order=mode==2?"LAU":"LARUQSF";
        for(U i=0;order[i]||events[i];i++) {
            if(order[i]!=events[i]){bad=1;break;}
        }
        if(mode!=2)for(U i=0;i<20;i++)if(seen[i]!=expected[i])bad=1;
        /* The real wrapper masks submit failure with the release return. */
        if(held||refs||(mode==2?(rc==0||calls):(rc!=0||calls!=1)))bad=1;
        printf("DDS_SUBMIT mode=%u rc=%d calls=%u events=%s bad=%u\n",mode,rc,calls,events,bad);
        if(bad)return 4;
    }
    const int expected_rc[]={0,-17,-7,-18,-19,-303,-301};
    for(mode=0;mode<7;mode++) {
        bad=held=refs=calls=count=0;events[0]=0;
        for(U i=0;i<20;i++)seen[i]=0;
        H target[4]={500,420,71,20};
        if(mode==5)target[0]=630; /* would overwrite beyond the target */
        if(mode==6)target[2]=72;  /* scaling is intentionally unsupported */
        struct native_submit_result result;
        int rc=native_submit(base,&source,src,target,&result);
        int submits=mode==0||mode==1||mode==4;
        const char *order=mode==6?"":mode==2?"LAU":submits?"LARUQSF":"LARUQF";
        for(U i=0;order[i]||events[i];i++)if(order[i]!=events[i]){bad=1;break;}
        if(submits)for(U i=0;i<20;i++)if(seen[i]!=expected[i])bad=1;
        if(held||refs||rc!=expected_rc[mode]||calls!=(U)submits)bad=1;
        printf("DDS_ADAPTER mode=%u rc=%d submit=%d release=%d calls=%u events=%s bad=%u\n",
            mode,rc,result.submit_rc,result.release_rc,calls,events,bad);
        if(bad)return 5;
    }
    /* Execute original all-disabled DDS raster path into bounded CPU memory.
     * No GPU copy is involved; this cannot prove transparent LCD erasure. */
    if(replace(base+0x68dc28,source_lock)||replace(base+0x68dc38,source_unlock))return 6;
    int (*raster)(U,void *,void *)=(void *)(base+0x7db4a1);
    U slots[24]={0};bad=0;
    for(U i=0;i<4;i++)blank.before[i]=blank.after[i]=0x5a5a5a5a;
    for(U i=0;i<288*32;i++)blank.pixels[i]=0xa55a;
    int rc=raster(0,slots,&source);
    U nonzero=0;for(U i=0;i<288*32;i++)if(blank.pixels[i])nonzero++;
    for(U i=0;i<4;i++)if(blank.before[i]!=0x5a5a5a5a||blank.after[i]!=0x5a5a5a5a)bad=1;
    printf("DDS_BLANK rc=%d nonzero=%u locked=%d bad=%u\n",rc,nonzero,source_locked,bad);
    if(rc||nonzero||source_locked||bad)return 7;
    printf("NATIVE_DDS_SUBMIT_OK original=3 adapter=7 blank=1 one_to_one errors_preserved\n");
    return 0;
}

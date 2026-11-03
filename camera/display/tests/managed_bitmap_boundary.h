/* OFFLINE ONLY. Original DDS allocate/free wrappers execute; memory/bitmap
 * ownership boundaries are simulated. No driver, camera or screen access. */
#include "../module/managed_buffer.h"
#define MANAGED_CASE_COUNT 4
extern int mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
static struct {H x,y,w,h;} mock_rect;
static struct {U before[16];unsigned char pixels[576*32];U after[16];} mock_memory;
static U mock_mode,mock_pool,mock_bitmap,mock_locked,mock_bad,event_count;
static char events[32];
static void event(char c){if(event_count<31)events[event_count++]=c;else mock_bad=1;events[event_count]=0;}
static int pool_create(U *request,U *out) {
    event('P');if(request[0]||request[1]!=0x156||request[2]||request[3]||request[4])mock_bad=1;
    if(mock_mode==1)return -7;mock_pool=1;*out=0xa7100001;return 0;
}
static int pool_free(U *request,U pool) {
    event('D');if(request[0]||request[1]!=0xffffffff||request[2]||pool!=0xa7100001||!mock_pool||mock_bitmap||mock_locked)mock_bad=1;
    mock_pool=0;return 0;
}
static int bitmap_create(U pool,U w,U h,U format,U flags,int a,int b,void **out,U c,U d) {
    event('B');if(pool!=0xa7100001||!mock_pool||w!=288||h!=32||format!=1||flags||a||b||c||d)mock_bad=1;
    if(mock_mode==2)return -7;
    mock_bitmap=1;mock_rect.x=mock_rect.y=0;mock_rect.w=mock_mode==4?280:288;mock_rect.h=32;*out=&mock_rect;return 0;
}
static int bitmap_rect(void *b,H **out){event('R');if(b!=&mock_rect||!mock_bitmap)mock_bad=1;*out=(H *)&mock_rect;return 0;}
static int bitmap_stride(void *b,short *out){event('S');if(b!=&mock_rect||!mock_bitmap)mock_bad=1;*out=576;return 0;}
static int bitmap_lock(void *b,int timeout,void **out) {
    event('L');if(b!=&mock_rect||!mock_bitmap||timeout||mock_locked)mock_bad=1;
    if(mock_mode==3)return -8;mock_locked=1;*out=mock_memory.pixels;return 0;
}
static int bitmap_unlock(void *b){event('U');if(b!=&mock_rect||!mock_locked)mock_bad=1;mock_locked=0;return 0;}
static int bitmap_free(void *b){event('F');if(b!=&mock_rect||!mock_bitmap||mock_locked)mock_bad=1;mock_bitmap=0;return 0;}
static int replace(U address,void *callback) {
    address&=~1U;U page=address&~4095U;
    if(mprotect((void *)page,8192,7))return 1;
    H *code=(H *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *literal=(void *)(address+4);U dest=(U)callback;
    for(U i=0;i<4;i++)literal[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5)!=0;
}
static int managed_prepare(U base) {
    return replace(base+0x68c212,pool_create)||replace(base+0x68c21e,pool_free)||
        replace(base+0x68d994,bitmap_create)||replace(base+0x68db58,bitmap_rect)||
        replace(base+0x68db90,bitmap_stride)||replace(base+0x68dc28,bitmap_lock)||
        replace(base+0x68dc38,bitmap_unlock)||replace(base+0x68dc58,bitmap_free);
}
#ifndef A7C_MANAGED_FRAME_FIXTURE
static int managed_case(int (*start)(void),int (*stop)(void),struct managed_state *m,U mode) {
    unsigned char *p=(void *)m;for(U i=0;i<sizeof *m;i++)p[i]=0;
    m->text.magic=0x41374d31;m->text.version=3;mock_mode=mode;
    mock_bad=mock_pool=mock_bitmap=mock_locked=event_count=0;events[0]=0;
    for(U i=0;i<16;i++)mock_memory.before[i]=mock_memory.after[i]=0x5a5a5a5a;
    int a=start(),b=stop();
    for(U i=0;i<16;i++)if(mock_memory.before[i]!=0x5a5a5a5a||mock_memory.after[i]!=0x5a5a5a5a)mock_bad=1;
    static const char *orders[]={"PBRSLUFD","P","PBD","PBRSLFD","PBRSFD"};
    const char *expected=orders[mode];U j=0;
    while(expected[j]&&events[j]&&expected[j]==events[j])j++;
    if(expected[j]!=events[j])mock_bad=1;
    printf("MANAGED_CASE mode=%u init_rc=%d exit_rc=%d events=%s bad=%u remaining=%u/%u/%u free=%d\n",
        mode,a,b,events,mock_bad,mock_pool,mock_bitmap,mock_locked,m->free_rc);
    return b||mock_bad||mock_pool||mock_bitmap||mock_locked||m->free_rc||
        (mode?(a==0):(a!=0))||m->text.delete_rc||m->text.unload_rc||m->text.init!=1||m->text.exit!=1;
}
#endif

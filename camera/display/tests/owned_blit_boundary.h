/* OFFLINE ONLY: native DDS wrappers/TextRM, simulated allocation and blit.
 * Frees are immediate in this fixture. It does NOT model native queued
 * reference retirement; see native_bitmap_release_fixture.c for that contract. */
#include "../module/managed_buffer.h"
extern int mprotect(void *,unsigned,int);
extern void __clear_cache(void *,void *);
#define MANAGED_CASE_COUNT 6
static struct slot {H rect[4];U pool,bitmap,locked;unsigned char pixels[MB_STRIDE*MB_H];} slots[2];
static U mode,bad,allocations,submissions,bitmap_allocations;
static int pool_create(U *request,U *out) {
    if(request[0]||request[1]!=0x156||request[2]||request[3]||request[4]||allocations>=2){bad++;return -1;}
    U i=allocations++;if(mode==1||(mode==4&&i==1))return -7;
    slots[i].pool=1;*out=0xa7100001+i;return 0;
}
static int pool_free(U *request,U pool) {
    U i=pool-0xa7100001;if(i>1){bad++;return -1;}
    if(request[0]||request[1]!=0xffffffff||request[2]||!slots[i].pool||slots[i].bitmap||slots[i].locked)bad++;
#ifdef SHARED_POOL_TRIAL
    if(i!=0||slots[1].bitmap||slots[1].locked)bad++;
#endif
    slots[i].pool=0;return 0;
}
static int bitmap_create(U pool,U w,U h,U format,U flags,int a,int b,void **out,U c,U d) {
#ifdef SHARED_POOL_TRIAL
    U i=bitmap_allocations++;if(i>1){bad++;return -1;}
    if(pool!=0xa7100001||!slots[0].pool||w!=MB_W||h!=MB_H||format!=1||flags||a||b||c||d)bad++;
    if(mode==4&&i==1)return -7;
#else
    U i=pool-0xa7100001;if(i>1){bad++;return -1;}
    if(!slots[i].pool||w!=MB_W||h!=MB_H||format!=1||flags||a||b||c||d)bad++;
#endif
    if(mode==2)return -7;
    slots[i].bitmap=1;slots[i].rect[2]=MB_W;slots[i].rect[3]=MB_H;*out=&slots[i];return 0;
}
static struct slot *check(void *p) {
    if(p!=&slots[0]&&p!=&slots[1]){bad++;return 0;}
    struct slot *s=p;if(!s->bitmap)bad++;return s;
}
static int bitmap_rect(void *p,H **out){struct slot *s=check(p);if(!s)return -1;*out=s->rect;return 0;}
static int bitmap_stride(void *p,short *out){if(!check(p))return -1;*out=MB_STRIDE;return 0;}
static int bitmap_lock(void *p,int timeout,void **out) {
    struct slot *s=check(p);if(!s)return -1;
    if(s->locked||(timeout!=0&&timeout!=200))bad++;
    if(mode==3||(mode==6&&timeout==200))return -11;
    s->locked=1;*out=s->pixels;return 0;
}
static int bitmap_unlock(void *p){struct slot *s=check(p);if(!s)return -1;if(!s->locked)bad++;s->locked=0;return 0;}
static int bitmap_free(void *p){struct slot *s=check(p);if(!s)return -1;if(s->locked)bad++;s->bitmap=0;return 0;}
static int blit(U a,U b,U *words,U c,U d) {
    submissions++;if(a||b||c||d)bad++;
    U expected[20]={0};
    expected[0]=(U)&slots[0];expected[3]=(U)&slots[1];expected[2]=expected[5]=0x00140047;
    expected[7]=(MB_H<<16)|MB_W;expected[8]=1;expected[9]=255;
    expected[15]=expected[16]=0x3f800000;
    for(U i=0;i<20;i++)if(expected[i]!=words[i]){printf("DESCRIPTOR_DIFFERENCE word=%u expected=%08x actual=%08x\n",i,expected[i],words[i]);bad++;}
    if(!slots[0].bitmap||!slots[1].bitmap||slots[0].locked||slots[1].locked)bad++;
    if(mode==5)return -23;
    for(U y=0;y<20;y++)for(U x=0;x<142;x++)slots[1].pixels[y*MB_STRIDE+x]=slots[0].pixels[y*MB_STRIDE+x];
    return 0;
}
static int replace(U address,void *callback) {
    address&=~1U;U page=address&~4095U;if(mprotect((void *)page,8192,7))return 1;
    H *code=(H *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *literal=(void *)(address+4);U dest=(U)callback;
    for(U i=0;i<4;i++)literal[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));return mprotect((void *)page,8192,5)!=0;
}
static int managed_prepare(U base) {
    return replace(base+0x68c212,pool_create)||replace(base+0x68c21e,pool_free)||replace(base+0x68d994,bitmap_create)||
        replace(base+0x68db58,bitmap_rect)||replace(base+0x68db90,bitmap_stride)||replace(base+0x68dc28,bitmap_lock)||
        replace(base+0x68dc38,bitmap_unlock)||replace(base+0x68dc58,bitmap_free)||replace(base+0x68ce02,blit);
}
static int managed_case(int (*start)(void),int (*stop)(void),struct managed_state *m,U trial_mode) {
    unsigned char *p=(void *)m;for(U i=0;i<sizeof *m;i++)p[i]=0;
    p=(void *)slots;for(U i=0;i<sizeof slots;i++)p[i]=0;
    m->text.magic=0x41374d31;
#ifdef SMALL_POOL_TRIAL
    m->text.version=6;
#elif defined(SHARED_POOL_TRIAL)
    m->text.version=5;
#else
    m->text.version=4;
#endif
    mode=trial_mode;bad=allocations=submissions=bitmap_allocations=0;
    int a=start(),b=stop();U remaining=0;
    for(U i=0;i<2;i++)remaining+=slots[i].pool+slots[i].bitmap+slots[i].locked;
    printf("MANAGED_CASE mode=%u init_rc=%d exit_rc=%d bad=%u remaining=%u submissions=%u compared=%u differences=%u\n",
        mode,a,b,bad,remaining,submissions,m->blit.compared,m->blit.differences);
    return b||bad||remaining||(mode?(a==0):(a!=0))||m->text.delete_rc||m->text.unload_rc||
        (!mode&&(submissions!=1||m->blit.compared!=2840||m->blit.differences||m->blit.padding_nonzero));
}

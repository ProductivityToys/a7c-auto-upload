/* Offline process only: initialize copied native runtime, then run exact DSO. */
#include "../module/text_state.h"
extern int printf(const char *,...);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern char *dlerror(void);
extern unsigned alarm(unsigned);
#ifdef A7C_MANAGED_BOUNDARY
#ifdef COMPOSE_TRIAL
#include "owned_blit_boundary.h"
#else
#include "managed_bitmap_boundary.h"
#endif
#endif
#ifdef A7C_BITMAP_BOUNDARY
extern int fflush(void *);
static unsigned short bitmap_pixels[72*24];
static int bitmap_trial(U base,const struct text_state *s) {
    /* Date-render caller rounds backing dimensions to multiples of eight. */
    for(U y=0;y<20;y++)for(U x=0;x<71;x++) {
        U off=TEXT_GUARD+y*s->stride+x*2;
        bitmap_pixels[y*72+x]=s->storage[off]|((U)s->storage[off+1]<<8);
    }
    void *bitmap=0;
    int (*wrap)(void **,void *,U,U)=(void *)(base+0x1fc3e1);
    int (*release)(void *)=(void *)(base+0x68dc59);
    int (*rectangle)(void *,H **)=(void *)(base+0x68db59);
    printf("BITMAP_BEGIN owned=72x24 visible=71x20\n");fflush(0);
    int rc=wrap(&bitmap,bitmap_pixels,71,20);
    printf("BITMAP_WRAP rc=%d object=%p\n",rc,bitmap);fflush(0);
    if(rc||!bitmap)return 7;
    H *rect=0;int queried=rectangle(bitmap,&rect);
    int valid=!queried&&rect&&rect[0]==0&&rect[1]==0&&rect[2]==71&&rect[3]==20;
    printf("BITMAP_RECT rc=%d valid=%d\n",queried,valid);fflush(0);
    int freed=release(bitmap);
    printf("BITMAP_RELEASE rc=%d\n",freed);fflush(0);
    if(!valid||freed)return 8;
    printf("TEXT_BITMAP_OK\n");return 0;
}
#endif
int main(void) {
    alarm(15);
    void *native=dlopen("/lab/libObj.so",1);
    if(!native){printf("NATIVE_LOAD %s\n",dlerror());return 1;}
    U address=(U)dlsym(native,"TextRM_loadFont");if(!address)return 2;
    int (*initialize)(void)=(void *)(address-0x57d271+0x57d8b9);
    if(initialize())return 3; /* lab only; never invoke this on camera */
#ifdef A7C_MANAGED_BOUNDARY
    if(managed_prepare(address-0x57d271))return 9;
#endif
    void *module=dlopen("/trial/marker.so",2);
    if(!module){printf("MODULE_LOAD %s\n",dlerror());return 4;}
    int (*start)(void)=dlsym(module,"IM_SAMPLE_SO_init");
    int (*stop)(void)=dlsym(module,"IM_SAMPLE_SO_exit");
    struct text_state *s=dlsym(module,"a7c_native_marker");
    if(!start||!stop||!s)return 5;
#ifdef A7C_MANAGED_BOUNDARY
    if(managed_case(start,stop,(void *)s,0))return 10;
    int a=0,b=0;
#else
    int a=start(),b=stop();
#endif
    printf("TEXT_MODULE rc=%d exit=%d init=%u exits=%u phase=%u load=%d create=%d bounds=%d draw=%d delete=%d unload=%d width=%u height=%u stride=%u bytes=%u guard=%u ink=%u aa=%u transparent=%u\n",
           a,b,s->init,s->exit,s->phase,s->load_rc,s->create_rc,s->bounds_rc,s->draw_rc,
           s->delete_rc,s->unload_rc,s->width,s->height,s->stride,s->bytes,s->guard_ok,s->ink,s->aa,s->transparent);
    if(a||b||s->init!=1||s->exit!=1||s->phase!=7||s->width!=71||s->height!=20||
       s->stride!=142||s->bytes!=2840||!s->guard_ok||!s->ink||!s->aa||!s->transparent)return 6;
    printf("PIXELS ");for(U i=0;i<s->bytes;i++)printf("%02x",s->storage[TEXT_GUARD+i]);
    printf("\nTEXT_MODULE_OK\n");
#ifdef A7C_MANAGED_BOUNDARY
    for(U mode=1;mode<=MANAGED_CASE_COUNT;mode++)if(managed_case(start,stop,(void *)s,mode))return 11;
    printf("MANAGED_BITMAP_BOUNDARY_OK %u\n",MANAGED_CASE_COUNT+1);
#endif
#ifdef A7C_BITMAP_BOUNDARY
    return bitmap_trial(address-0x57d271,s);
#else
    return 0;
#endif
}

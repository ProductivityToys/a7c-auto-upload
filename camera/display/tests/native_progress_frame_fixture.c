/* Offline integration: actual TextRM rasterizer + candidate frame + descriptor.
 * Memory ownership, native front and GPU copying are simulated, NOT hardware. */
#include "../module/text_state.h"
extern int printf(const char *,...);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern unsigned alarm(unsigned);
#define A7C_MANAGED_FRAME_FIXTURE 1
#include "managed_bitmap_boundary.h"
static void *native;
#define TextRM_loadFont frame_load
#define TextRM_unloadFont frame_unload
#define TextRM_createText frame_create
#define TextRM_getBounds frame_bounds
#define TextRM_drawText frame_draw
#define TextRM_deleteText frame_delete
#define A7C_NATIVE_SUBMIT_OFFLINE 1
#include "../module/native_progress_frame.h"
int frame_load(const char *s,U *f){int (*fn)(const char *,U *)=dlsym(native,"TextRM_loadFont");return fn(s,f);}
int frame_unload(U f){int (*fn)(U)=dlsym(native,"TextRM_unloadFont");return fn(f);}
int frame_create(const char *s,U a,U b,void *c,short d,U *t){int (*fn)(const char *,U,U,void *,short,U *)=dlsym(native,"TextRM_createText");return fn(s,a,b,c,d,t);}
int frame_bounds(U t,void *d){int (*fn)(U,void *)=dlsym(native,"TextRM_getBounds");return fn(t,d);}
int frame_draw(U t,void *d,void *p,U *c){int (*fn)(U,void *,void *,U *)=dlsym(native,"TextRM_drawText");return fn(t,d,p,c);}
int frame_delete(U t){int (*fn)(U)=dlsym(native,"TextRM_deleteText");return fn(t);}
static H screen[640*480],front_rect[4]={0,0,640,480};
static U front,held,refs,submits,submit_failure;
static int enter(void){if(held)mock_bad=1;held=1;return 0;}
static int leave(void){if(!held)mock_bad=1;held=0;return 0;}
static int acquire(void **p){if(!held)mock_bad=1;*p=&front;return 0;}
static int retain(void *p){if(!held||p!=&front)mock_bad=1;refs++;return 0;}
static int release(void *p){
    if(p==&front){if(held||refs!=1)mock_bad=1;refs--;return 0;}
    return bitmap_free(p);
}
static int rectangle(void *p,H **r){
    if(p==&front){if(held||refs!=1)mock_bad=1;*r=front_rect;return 0;}
    return bitmap_rect(p,r);
}
static int submit(U a,U b,const U *d,U c,U e) {
    if(a||b||c||e||held||refs!=1||mock_locked||!mock_bitmap)mock_bad=1;
    const U expected[20]={(U)&mock_rect,0,(20U<<16)|78,(U)&front,
        (432U<<16)|562,(20U<<16)|78,0,(480U<<16)|640,1,255,
        0,0,0,0,0,0x3f800000,0x3f800000,0,0,0};
    for(U i=0;i<20;i++)if(d[i]!=expected[i])mock_bad=1;
    submits++;
    if(submit_failure)return -17;
    /* Replacement semantics, deliberately not a real GPU rendering test. */
    for(U y=0;y<20;y++)for(U x=0;x<78;x++) {
        U i=y*576+x*2;
        screen[(432+y)*640+562+x]=mock_memory.pixels[i]|((U)mock_memory.pixels[i+1]<<8);
    }
    return 0;
}
static int run(U base,int percent,U failure) {
    mock_bad=mock_pool=mock_bitmap=mock_locked=event_count=held=refs=submits=0;
    events[0]=0;mock_mode=failure<=4?failure:0;submit_failure=failure==5;
    for(U i=0;i<16;i++)mock_memory.before[i]=mock_memory.after[i]=0x5a5a5a5a;
    struct progress_frame_result r;
    int rc=native_progress_frame(base,percent,&r);
    if(mock_pool||mock_bitmap||mock_locked||held||refs)mock_bad=1;
    for(U i=0;i<16;i++)if(mock_memory.before[i]!=0x5a5a5a5a||mock_memory.after[i]!=0x5a5a5a5a)mock_bad=1;
    if(failure){if(!rc||submits!=(failure==5?1U:0U))mock_bad=1;}
    else if(percent < -1 || percent > 99){if(rc!=-401||event_count||submits)mock_bad=1;}
    else {
        if(rc||submits!=1||r.delete_rc||r.unload_rc)mock_bad=1;
        U ink=0,aa=0;
        for(U y=0;y<480;y++)for(U x=0;x<640;x++) {
            H value=screen[y*640+x];
            if(y>=432&&y<452&&x>=562) {
                if(percent<0||x>=562+r.width){if(value)mock_bad=1;}
                else {if(value)ink++;if((value&15)&&((value&15)<15))aa++;}
            } else if(value!=0x1234)mock_bad=1;
        }
        if(percent>=0 && (!ink||!aa||r.height!=20||r.width!=(percent<10?60U:71U)))mock_bad=1;
    }
    printf("PROGRESS_FRAME percent=%d failure=%u rc=%d width=%u submits=%u events=%s bad=%u\n",
        percent,failure,rc,r.width,submits,events,mock_bad);
    return mock_bad!=0;
}
int main(void) {
    alarm(20);native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    U address=(U)dlsym(native,"TextRM_loadFont");if(!address)return 2;
    U base=address-0x57d271;
    int (*initialize)(void)=(void *)(base+0x57d8b9);
    if(initialize()||managed_prepare(base))return 3;
    if(replace(base+0x68dc58,release)||replace(base+0x68db58,rectangle)||
       replace(base+0x75ccf4,enter)||replace(base+0x75cce4,leave)||
       replace(base+0x75cca4,acquire)||replace(base+0x68dc48,retain)||
       replace(base+0x68ce02,submit))return 4;
    for(U i=0;i<640*480;i++)screen[i]=0x1234;
    /* Exercise every label plus shrinking two digits to one without a blank. */
    for(int p=99;p>=0;p--)if(run(base,p,0))return 5;
    if(run(base,42,0)||run(base,-1,0))return 6;
    for(U failure=1;failure<=5;failure++)if(run(base,42,failure))return 7;
    if(run(base,-2,0)||run(base,100,0))return 8;
#ifdef A7C_PROGRESS_MODULE
    void *module=dlopen("/trial/marker.so",2);if(!module)return 9;
    int (*start)(void)=dlsym(module,"IM_SAMPLE_SO_init");
    int (*stop)(void)=dlsym(module,"IM_SAMPLE_SO_exit");
    if(!start||!stop)return 10;
    mock_bad=mock_pool=mock_bitmap=mock_locked=event_count=held=refs=submits=0;
    mock_mode=submit_failure=0;events[0]=0;
    int started=start();
    U ink=0;for(U y=432;y<452;y++)for(U x=562;x<640;x++)if(screen[y*640+x])ink++;
    if(started||!ink||submits!=1||mock_pool||mock_bitmap||mock_locked||held||refs)return 11;
    if(start()!=-1||submits!=1)return 12;
    /* The module has returned to its caller before stop, not slept inside init. */
#ifdef A7C_FRAME_EXTERNAL_REDRAW
    if(stop()||submits!=1||mock_pool||mock_bitmap||mock_locked||held||refs)return 13;
    /* Exit must not erase pixels in a potentially changed page. Native redraw
     * is the external controller's responsibility, not simulated as a GPU call. */
    U kept=0;for(U y=432;y<452;y++)for(U x=562;x<640;x++)if(screen[y*640+x])kept++;
    if(kept!=ink||stop()||submits!=1||mock_bad)return 14;
    printf("NATIVE_PROGRESS_EXTERNAL_REDRAW module_did_not_clear=1\n");
#else
    if(stop()||submits!=2||mock_pool||mock_bitmap||mock_locked||held||refs)return 13;
    for(U y=0;y<480;y++)for(U x=0;x<640;x++)
        if(screen[y*640+x]!=(y>=432&&y<452&&x>=562?0:0x1234))return 14;
    if(stop()||submits!=2||mock_bad)return 15;
#endif
    printf("NATIVE_PROGRESS_MODULE_OK init/reinit/exit/reexit source_leaks=0\n");
    printf("NATIVE_PROGRESS_FRAME_OK 113\n");
#else
    printf("NATIVE_PROGRESS_FRAME_OK 109\n");
#endif
    return 0;
}

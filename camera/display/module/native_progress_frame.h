/* ILCE-7C 2.00 research candidate. Offline only; not used by the uploader.
 * One DDS source per frame, current native front as target, no target pool.
 * Caller must exclude native DDS output and validate an empty shooting region.
 * percent=-1 clears the SAME 78x20 region; this is not a saved-background restore.
 * No sleeps/threads/timers, global TextRM init or font/code patches.
 */
#if !defined(A7C_NATIVE_SUBMIT_OFFLINE) && !defined(A7C_NATIVE_SCREEN_TRIAL)
#error Native progress frame is not enabled for camera deployment
#endif
#include "text_state.h"
#include "native_submit.h"
extern int TextRM_loadFont(const char *,U *),TextRM_unloadFont(U);
extern int TextRM_createText(const char *,U,U,void *,short,U *);
extern int TextRM_getBounds(U,void *),TextRM_drawText(U,void *,void *,U *);
extern int TextRM_deleteText(U);
struct progress_frame_result {
    U width,height,submit_attempted;
    int font_rc,text_rc,bounds_rc,draw_rc,delete_rc,unload_rc;
    int allocate_rc,rectangle_rc,stride_rc,lock_rc,unlock_rc,free_rc;
    struct native_submit_result submit;
    U source_ink,source_aa;
};
static int native_progress_frame(U base,int percent,struct progress_frame_result *r) {
    /* Keep the existing shooting placement, without its x2/y6 font scaling. */
    const H src[4]={0,0,78,20},dst[4]={562,432,78,20};
    for(U i=0;i<sizeof *r;i++)((volatile unsigned char *)r)[i]=0;
    r->submit.acquire_rc=r->submit.rectangle_rc=r->submit.submit_rc=r->submit.release_rc=-999;
    if(percent < -1 || percent > 99)return -401;
    int (*allocate)(U,U *,void **)=(void *)(base+0x7db2d1);
    int (*free_both)(U,U,void *)=(void *)(base+0x7db569);
    int (*free_pool)(void *,U)=(void *)(base+0x68c21f);
    int (*rectangle)(void *,H **)=(void *)(base+0x68db59);
    int (*stride_query)(void *,short *)=(void *)(base+0x68db91);
    int (*lock)(void *,int,void **)=(void *)(base+0x68dc29);
    int (*unlock)(void *)=(void *)(base+0x68dc39);
    struct {H width,height;U stride;} d={0};
    U font=0,text=0,pool=0,changed=0;
    int have_font=0,have_text=0,rc=0;
    void *bitmap=0,*pixels=0;H *rect=0;short stride=0;
    if(percent>=0) {
        char label[7]={'U','D',' ',0,0,0,0};
        U n=3;if(percent>=10)label[n++]=(char)('0'+percent/10);
        label[n++]=(char)('0'+percent%10);label[n]='%';
        rc=r->font_rc=TextRM_loadFont("FONT_UNIVERS",&font);
        if(rc)goto done;
        have_font=1;
        U attr[12];for(U i=0;i<12;i++)((volatile U *)attr)[i]=0;
        attr[0]=font;attr[1]=1;attr[2]=(20U<<16)|20U;attr[3]=1;attr[4]=0xffffffff;
        rc=r->text_rc=TextRM_createText(label,0,0x8ff,attr,0,&text);
        if(rc)goto done;
        have_text=1;
        rc=r->bounds_rc=TextRM_getBounds(text,&d);
        if(rc)goto done;
        r->width=d.width;r->height=d.height;
        if(!d.width||d.width>78||d.height!=20||d.stride!=2U*d.width){rc=-402;goto done;}
    }
    rc=r->allocate_rc=allocate(0,&pool,&bitmap);
    if(rc)goto done;
    if(!pool||!bitmap){rc=-403;goto done;}
    rc=r->rectangle_rc=rectangle(bitmap,&rect);
    if(rc)goto done;
    rc=r->stride_rc=stride_query(bitmap,&stride);
    if(rc)goto done;
    if(!rect||rect[0]||rect[1]||rect[2]!=288||rect[3]!=32||stride!=576){rc=-404;goto done;}
    rc=r->lock_rc=lock(bitmap,0,&pixels);
    if(rc)goto done;
    if(!pixels)rc=-405;
    else {
        /* Full source clear removes stale trailing digits before every frame. */
        for(U i=0;i<576U*32;i++)((unsigned char *)pixels)[i]=0;
        if(percent>=0) {
            d.stride=576;
            rc=r->draw_rc=TextRM_drawText(text,&d,pixels,&changed);
            const unsigned char *s=pixels;
            for(U y=0;y<20;y++)for(U x=0;x<78;x++) {
                U v=s[y*576+x*2]|((U)s[y*576+x*2+1]<<8);
                if(v)r->source_ink++;
                if((v&15)&&(v&15)<15)r->source_aa++;
            }
        }
    }
    r->unlock_rc=unlock(bitmap);
    if(!rc)rc=r->unlock_rc;
    if(rc)goto done;
    r->submit_attempted=1;
    rc=native_submit(base,bitmap,src,dst,&r->submit);
done:
    /* Follow the original sequential DDS source lifetime. Driver close is not
     * simulated by successful CPU tests and still needs a separate live trial. */
    if(bitmap&&pool)r->free_rc=free_both(0,pool,bitmap);
    else if(pool){U request[3]={0,0xffffffff,0};r->free_rc=free_pool(request,pool);}
    if(have_text)r->delete_rc=TextRM_deleteText(text);
    if(have_font)r->unload_rc=TextRM_unloadFont(font);
    if(!rc)rc=r->free_rc?r->free_rc:r->delete_rc?r->delete_rc:r->unload_rc;
    return rc;
}

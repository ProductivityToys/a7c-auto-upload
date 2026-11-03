/* Owned DDS source; COMPOSE_TRIAL adds private blit (offline-only after driver BUG).
 * No screen target acquisition. */
#include "text_state.h"
#ifdef SMALL_POOL_TRIAL
#define MB_W 72U
#define MB_H 24U
#else
#define MB_W 288U
#define MB_H 32U
#endif
#define MB_STRIDE (MB_W*2U)
#ifdef COMPOSE_TRIAL
extern int GRM_bitmapGetSubRectangle(void *,H **);
extern int GRM_bitmapWriteLockBits(void *,int,void **);
extern int GRM_bitmapWriteUnlockBits(void *);
#include "owned_blit.h"
#endif
struct managed_state {
    struct text_state text;
    U stage;
    int allocate_rc,rectangle_rc,stride_rc,lock_rc,unlock_rc,free_rc;
    U width,height,stride,padding_nonzero,pool,bitmap;
#ifdef COMPOSE_TRIAL
    struct blit_state blit;
#endif
};
#ifdef A7C_MANAGED_IMPLEMENTATION
extern int GRM_bitmapGetSubRectangle(void *,H **);
extern int GRM_bitmapWriteLockBits(void *,int,void **);
extern int GRM_bitmapWriteUnlockBits(void *);
static int managed_draw(struct managed_state *m,U base,U text,struct dimensions *d,U *changed) {
#ifdef SMALL_POOL_TRIAL
    int (*pool_create)(void *,U *)=(void *)(base+0x68c213);
#else
    int (*allocate)(U,U *,void **)=(void *)(base+0x7db2d1);
#endif
    int (*free_both)(U,U,void *)=(void *)(base+0x7db569);
    int (*free_pool)(void *,U)=(void *)(base+0x68c21f);
    int (*stride_query)(void *,short *)=(void *)(base+0x68db91);
    U pool=0;void *bitmap=0,*pixels=0;H *rect=0;short stride=0;
    m->allocate_rc=m->rectangle_rc=m->stride_rc=m->lock_rc=m->unlock_rc=m->free_rc=-999;
    m->stage=1;
#ifdef SMALL_POOL_TRIAL
    U request[5]={0,0x156,0,0,0};
    m->allocate_rc=pool_create(request,&pool);
    if(!m->allocate_rc)m->allocate_rc=GRM_bitmapCreate(pool,MB_W,MB_H,1,0,0,0,&bitmap,0,0);
#else
    m->allocate_rc=allocate(0,&pool,&bitmap);
#endif
    m->pool=pool;m->bitmap=(U)bitmap;
    int rc=-101;
    if(!m->allocate_rc && pool && bitmap) {
        m->stage=2;
        m->rectangle_rc=GRM_bitmapGetSubRectangle(bitmap,&rect);
        m->stride_rc=stride_query(bitmap,&stride);
        if(!m->rectangle_rc && rect && !m->stride_rc) {
            m->width=rect[2];m->height=rect[3];m->stride=(U)stride;
            if(!rect[0] && !rect[1] && rect[2]==MB_W && rect[3]==MB_H && stride==MB_STRIDE &&
               d->width<=MB_W && d->height==20) {
                m->stage=3;
                m->lock_rc=GRM_bitmapWriteLockBits(bitmap,0,&pixels); /* never wait for another owner */
                if(!m->lock_rc) {
                    if(pixels) {
                        unsigned char *p=pixels;
                        for(U i=0;i<MB_STRIDE*MB_H;i++)p[i]=0;
                        struct dimensions destination=*d;destination.stride=MB_STRIDE;
                        m->stage=4;
                        rc=TextRM_drawText(text,&destination,pixels,changed);
                        for(U y=0;y<MB_H;y++)for(U x=0;x<MB_STRIDE;x++) {
                            if(y<d->height && x<d->width*2U)
                                m->text.storage[TEXT_GUARD+y*d->stride+x]=p[y*MB_STRIDE+x];
                            else if(p[y*MB_STRIDE+x])m->padding_nonzero++;
                        }
                        if(m->padding_nonzero)rc=-102;
                    }
                    m->stage=5;m->unlock_rc=GRM_bitmapWriteUnlockBits(bitmap);
                    if(m->unlock_rc)rc=-103;
                }
            }
        }
    }
#ifdef COMPOSE_TRIAL
    if(!rc)rc=owned_blit(&m->blit,base,pool,bitmap,&m->text);
#endif
    /* DDS allocation can leave its pool if bitmap creation fails. */
    m->stage=6;
    if(bitmap && pool)m->free_rc=free_both(0,pool,bitmap);
    else if(pool) { U request[3]={0,0xffffffff,0};m->free_rc=free_pool(request,pool); }
    else m->free_rc=0;
    if(m->free_rc)rc=-104;
    else {m->pool=0;m->bitmap=0;}
    m->stage=7;return rc;
}
#endif

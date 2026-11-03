/* OFFLINE RESEARCH ONLY: live trial hit grm_ma/dmm close kernel BUG.
 * Synchronous completion precedes command reference retirement; release()==0
 * only means decrement succeeded. Native pool close separately waits for
 * allocated blocks to retire, so that ordering alone does NOT prove a race
 * or explain the kernel BUG. Never re-enable live execution merely because
 * the immediate-release boundary fixture passes. */
struct blit_state {
    U stage,pool,bitmap,compared,differences,padding_nonzero;
    int allocate_rc,rectangle_rc,stride_rc,clear_lock_rc,clear_unlock_rc;
    int submit_rc,read_lock_rc,read_unlock_rc,free_rc;
};
#ifdef A7C_MANAGED_IMPLEMENTATION
extern int GRM_gpermRectblit(U,U,void *,U,U);
extern int GRM_bitmapCreate(U,U,U,U,U,int,int,void **,U,U);
static int owned_blit(struct blit_state *s,U base,U source_pool,void *source,const struct text_state *text) {
#ifdef SHARED_POOL_TRIAL
    int (*free_bitmap)(void *)=(void *)(base+0x68dc59);
#else
    (void)source_pool;
    int (*allocate)(U,U *,void **)=(void *)(base+0x7db2d1);
    int (*free_both)(U,U,void *)=(void *)(base+0x7db569);
    int (*free_pool)(void *,U)=(void *)(base+0x68c21f);
#endif
    int (*stride_query)(void *,short *)=(void *)(base+0x68db91);
    U pool=0;void *bitmap=0,*pixels=0;H *rect=0;short stride=0;int rc=-201;
    s->allocate_rc=s->rectangle_rc=s->stride_rc=s->clear_lock_rc=s->clear_unlock_rc=
        s->submit_rc=s->read_lock_rc=s->read_unlock_rc=s->free_rc=-999;
    s->stage=1;
#ifdef SHARED_POOL_TRIAL
    pool=source_pool;s->allocate_rc=GRM_bitmapCreate(pool,MB_W,MB_H,1,0,0,0,&bitmap,0,0);
#else
    s->allocate_rc=allocate(0,&pool,&bitmap);
#endif
    s->pool=pool;s->bitmap=(U)bitmap;
    if(!s->allocate_rc && pool && bitmap && bitmap!=source) {
        s->stage=2;s->rectangle_rc=GRM_bitmapGetSubRectangle(bitmap,&rect);
        s->stride_rc=stride_query(bitmap,&stride);
        if(!s->rectangle_rc && rect && !s->stride_rc && !rect[0] && !rect[1] &&
           rect[2]==MB_W && rect[3]==MB_H && stride==MB_STRIDE) {
            s->stage=3;s->clear_lock_rc=GRM_bitmapWriteLockBits(bitmap,0,&pixels);
            if(!s->clear_lock_rc) {
                if(pixels)for(U i=0;i<MB_STRIDE*MB_H;i++)((unsigned char *)pixels)[i]=0;
                s->clear_unlock_rc=GRM_bitmapWriteUnlockBits(bitmap);
                if(pixels && !s->clear_unlock_rc) {
                    U descriptor[20];for(U i=0;i<20;i++)((volatile U *)descriptor)[i]=0;
                    descriptor[0]=(U)source;descriptor[3]=(U)bitmap;
                    descriptor[2]=descriptor[5]=(text->height<<16)|text->width;
                    descriptor[7]=(MB_H<<16)|MB_W;descriptor[8]=1;descriptor[9]=255;
                    descriptor[15]=descriptor[16]=0x3f800000;
                    s->stage=4;s->submit_rc=GRM_gpermRectblit(0,0,descriptor,0,0);
                    if(!s->submit_rc) {
                        pixels=0;s->stage=5;
                        s->read_lock_rc=GRM_bitmapWriteLockBits(bitmap,200,&pixels);
                        if(!s->read_lock_rc) {
                            if(pixels) {
                                const unsigned char *p=pixels;
                                for(U y=0;y<MB_H;y++)for(U x=0;x<MB_STRIDE;x++) {
                                    if(y<text->height && x<text->stride) {
                                        s->compared++;
                                        if(p[y*MB_STRIDE+x]!=text->storage[TEXT_GUARD+y*text->stride+x])s->differences++;
                                    } else if(p[y*MB_STRIDE+x])s->padding_nonzero++;
                                }
                            }
                            s->read_unlock_rc=GRM_bitmapWriteUnlockBits(bitmap);
                            if(!s->read_unlock_rc && s->compared==text->bytes && !s->differences && !s->padding_nonzero)rc=0;
                        }
                    }
                }
            }
        }
    }
    s->stage=6;
#ifdef SHARED_POOL_TRIAL
    s->free_rc=bitmap?free_bitmap(bitmap):0; /* borrowed pool remains with source */
#else
    if(bitmap && pool)s->free_rc=free_both(0,pool,bitmap);
    else if(pool){U request[3]={0,0xffffffff,0};s->free_rc=free_pool(request,pool);}
    else s->free_rc=0;
#endif
    /* Zero handles describe our released reference, NOT final destruction. */
    if(s->free_rc)rc=-202;else{s->pool=0;s->bitmap=0;}
    s->stage=7;return rc;
}
#endif

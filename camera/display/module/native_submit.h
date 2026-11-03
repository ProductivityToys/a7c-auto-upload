/* Experimental candidate for ILCE-7C 2.00 only; not used by the uploader.
 * Caller owns the source bitmap and validates the active UI/placement.
 * Mirror 0x68d13c target acquisition and descriptor, keeping the GRM result.
 * Native command execution itself discards a deeper backend result; rc==0
 * therefore is NOT proof of pixel rendering. Validate display via capture.
 * No allocation, pool close, font patch, scaling, timer or background work. */
#if !defined(A7C_NATIVE_SUBMIT_OFFLINE) && !defined(A7C_NATIVE_SCREEN_TRIAL)
#error Native submit is not enabled for camera deployment
#endif
struct native_submit_result {
    int acquire_rc,rectangle_rc,submit_rc,release_rc;
    U target,before_ink,after_ink;
    int before_read_rc,after_read_rc;
};
#ifdef A7C_NATIVE_SCREEN_TRIAL
static int native_region_ink(U base,void *front,const H *rect,U *ink) {
    const volatile U *obj=front;
    if(obj[0]!=base+0x13b1f50||obj[1]<0x10000||obj[1]>0x7fffffc0)return -1;
    const volatile U *desc=(const void *)obj[1];
    if(desc[4]!=((480U<<16)|640)||desc[6]!=desc[4]||desc[7]!=1||desc[9]!=0xfe33a000||
       obj[2]<0x1000000||obj[2]>0x7ff6a000||rect[0]!=562||rect[1]!=432||rect[2]!=78||rect[3]!=20)return -2;
    const volatile H *pixels=(const void *)obj[2];*ink=0;
    for(U y=432;y<452;y++)for(U x=562;x<640;x++)if(pixels[y*640+x])(*ink)++;
    return 0;
}
#endif
static int native_submit(U base,void *source,const H *src,const H *dst,
                         struct native_submit_result *result) {
    result->acquire_rc=result->rectangle_rc=result->submit_rc=result->release_rc=-999;
    result->target=result->before_ink=result->after_ink=0;
    result->before_read_rc=result->after_read_rc=-999;
    if(!source||!src||!dst||!src[2]||!src[3]||
       src[2]!=dst[2]||src[3]!=dst[3])return -301;
    int (*enter)(void)=(void *)(base+0x75ccf5);
    int (*leave)(void)=(void *)(base+0x75cce5);
    int (*acquire)(void **)=(void *)(base+0x75cca5);
    int (*retain)(void *)=(void *)(base+0x68dc49);
    int (*release)(void *)=(void *)(base+0x68dc59);
    int (*rectangle)(void *,H **)=(void *)(base+0x68db59);
    int (*submit)(U,U,const U *,U,U)=(void *)(base+0x68ce03);
    void *front=0;
    enter();
    result->acquire_rc=acquire(&front);
    if(!result->acquire_rc && front)retain(front);
    leave();
    if(result->acquire_rc)return result->acquire_rc;
    if(!front)return -302;
    result->target=(U)front;
    H *clip=0;
    int rc=result->rectangle_rc=rectangle(front,&clip);
    if(!rc) {
        if(!clip||dst[0]<clip[0]||dst[1]<clip[1]||
           (U)dst[0]+dst[2]>(U)clip[0]+clip[2]||
           (U)dst[1]+dst[3]>(U)clip[1]+clip[3])rc=-303;
        else {
            U desc[20];for(U i=0;i<20;i++)((volatile U *)desc)[i]=0;
            desc[0]=(U)source;desc[3]=(U)front;
            desc[1]=src[0]|((U)src[1]<<16);desc[2]=src[2]|((U)src[3]<<16);
            desc[4]=dst[0]|((U)dst[1]<<16);desc[5]=dst[2]|((U)dst[3]<<16);
            desc[6]=clip[0]|((U)clip[1]<<16);desc[7]=clip[2]|((U)clip[3]<<16);
            desc[8]=1;desc[9]=255;desc[15]=desc[16]=0x3f800000;
#ifdef A7C_NATIVE_SCREEN_TRIAL
            result->before_read_rc=native_region_ink(base,front,dst,&result->before_ink);
#endif
            rc=result->submit_rc=submit(0,0,desc,0,0);
#ifdef A7C_NATIVE_SCREEN_TRIAL
            result->after_read_rc=native_region_ink(base,front,dst,&result->after_ink);
#endif
        }
    }
    result->release_rc=release(front);
    return rc?rc:result->release_rc;
}

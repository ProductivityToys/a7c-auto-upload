/* Offline candidate only: native DDS effective-slot input -> one native glyph
 * cache -> submission on EACH existing DDS refresh. No new timer, fence, thread
 * or bitmap ownership. The caller supplies raster and submit implementations.
 * This is not a live hook: installation, original forwarding and page changes
 * still require an integration contract before camera deployment. */
#ifndef A7C_DDS_REFRESH_OFFLINE
#error DDS native refresh has no live installer
#endif
#define DDS_NATIVE_PIXELS (78U*20U)
struct dds_native_refresh {
    int valid,percent,owned;
    H pixels[DDS_NATIVE_PIXELS];
};
/* Return -2 for an unowned payload, -1 for all slots disabled, else 0..99.
 * Disabled native slots contain uninitialized payload bytes: inspect only flag.
 * Only slot 0, white, at the currently supported shooting position is ours. */
static int dds_native_percent(const unsigned char *slots,const H *position) {
    if(!slots||!position||position[0]!=562||position[1]!=432)return -2;
    for(U i=1;i<8;i++)if(slots[i*12+8])return -2;
    if(!slots[8])return -1;
    if(slots[8]!=1||slots[10]!=255||slots[11]!=255)return -2;
    if((slots[0]>>4)!=1||(slots[1]&15)!=12)return -2;
    for(U i=2;i<8;i++)if(slots[i])return -2;
    U tens=slots[0]&15,ones=slots[1]>>4;
    if(ones<2||ones>11||(tens!=0&&(tens<3||tens>11)))return -2;
    return (tens?(tens-2)*10:0)+ones-2;
}
/* handled==0 means the unchanged native renderer must receive this request.
 * Pixels are RGBA4444 at 1:1 size; cache only the last progress value (3120 B).
 * Raster failure invalidates the cache and never submits partial pixels.
 * Native DDS clears its visible flag before calling the renderer: integration
 * must restore that flag on failed owned clear (same DDS thread) to retry on
 * the existing refresh. This helper has no native-state pointer.
 * Submission failure is returned; retry can reuse a successfully rasterized
 * cache. Clear submits one zero tile, then drops ownership on success. */
static int dds_native_refresh_run(struct dds_native_refresh *s,
        const unsigned char *slots,const H *position,
        int (*raster)(int,H *),int (*submit)(const H *,int),int *handled) {
    *handled=0;
    int percent=dds_native_percent(slots,position);
    if(percent==-2||(percent==-1&&!s->owned))return 0;
    *handled=1;
    if(percent==-1) {
        for(U i=0;i<DDS_NATIVE_PIXELS;i++)s->pixels[i]=0;
        s->valid=0;
        int rc=submit(s->pixels,1);
        if(!rc)s->owned=0;
        return rc;
    }
    if(!s->valid||s->percent!=percent) {
        s->valid=0;
        for(U i=0;i<DDS_NATIVE_PIXELS;i++)s->pixels[i]=0;
        int rc=raster(percent,s->pixels);
        if(rc)return rc;
        s->percent=percent;s->valid=1;
    }
    int rc=submit(s->pixels,0);
    if(!rc)s->owned=1;
    return rc;
}

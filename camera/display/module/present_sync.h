/* Single-shot diagnostic: one owned fence, one finite wait, one destroy.
 * Not a renderer or a per-frame policy. A timeout never permits pixel writes.
 * The finite timeout bounds the condition wait, not every driver/mutex call.
 * Original BindTextureManager fences remain entirely owned by Sony. */
#ifndef A7C_PRESENT_SYNC_H
#define A7C_PRESENT_SYNC_H
#if !defined(A7C_PRESENT_SYNC_OFFLINE) && !defined(PRESENT_SYNC_TRIAL)
#error "Native synchronization diagnostic requires an explicit trial build"
#endif
struct present_sync_result {
    unsigned created,wait_result,poll_result,destroy_result;
};
static int present_sync_once(unsigned base,unsigned display,
                             struct present_sync_result *result) {
    void *(*create)(unsigned,unsigned,const int *)=(void *)(base+0x785a71);
    unsigned (*wait)(unsigned,void *,unsigned,unsigned long long)=(void *)(base+0x785671);
    unsigned (*destroy)(unsigned,void *)=(void *)(base+0x7858e1);
    result->created=result->wait_result=result->poll_result=result->destroy_result=0;
    if(display!=1)return -1;
    void *sync=create(display,0x30f9,0);
    if(!sync)return -2;
    result->created=1;
    /* EGL_SYNC_FLUSH_COMMANDS_BIT_KHR; nanoseconds, 20 ms, never FOREVER. */
    result->wait_result=wait(display,sync,1,20000000ULL);
    /* This firmware maps an interrupted condition wait to SATISFIED without
     * checking the fence state again. One zero-time/zero-flush query checks
     * that state; it does not add a retry or another blocking wait. */
    if(result->wait_result==0x30f6)result->poll_result=wait(display,sync,0,0ULL);
    result->destroy_result=destroy(display,sync);
    if(result->destroy_result!=1)return -3;
    if(result->wait_result==0x30f5||result->poll_result==0x30f5)return 1;
    return result->wait_result==0x30f6&&result->poll_result==0x30f6?0:-4;
}
#endif

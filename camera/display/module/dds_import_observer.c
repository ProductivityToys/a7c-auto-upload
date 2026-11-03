/* ILCE-7C 2.00, passive DDS import observer. Offline build only until external
 * pointer recovery and map-permission validation are added to the controller.
 * No source/target pixel reads or writes, allocation, timers or upload calls. */
#include "dds_import_handoff.h"
typedef unsigned U;
extern int TextRM_loadFont(const char *,U *),syscall(int,...);
#define API __attribute__((visibility("default")))
#define SAMPLES 8U
struct sample {
    U ready,kind,caller,tid,source,target,src_size,dst_xy,dst_size;
    int original_rc;
};
API struct {
    U magic,version,init,exit,suspend,resume,inactive,active;
    int prepare_rc,install_rc,restore_rc;
    U count;
    struct sample samples[SAMPLES];
} a7c_native_marker={.magic=0x41374d31,.version=15,
    .prepare_rc=-999,.install_rc=-999,.restore_rc=-999};
static U base;
static struct dds_import_handoff hooks;
static struct sample *reserve(U kind,U caller) {
    if(!__atomic_load_n(&hooks.enabled,__ATOMIC_ACQUIRE))return 0;
    U n=__atomic_load_n(&a7c_native_marker.count,__ATOMIC_RELAXED);
    do {
        if(n>=SAMPLES)return 0;
    } while(!__atomic_compare_exchange_n(&a7c_native_marker.count,&n,n+1,0,
                                         __ATOMIC_RELAXED,__ATOMIC_RELAXED));
    struct sample *s=&a7c_native_marker.samples[n];
    s->kind=kind;s->caller=caller;s->tid=(U)syscall(224);return s;
}
__attribute__((noinline)) static int unlock_entry(void *bitmap) {
    U caller=(U)__builtin_return_address(0);
    struct sample *s=caller==base+0x7db4fb?reserve(1,caller):0;
    if(s)s->source=(U)bitmap;
    int (*original)(void *)=(void *)hooks.original[0];
    int rc=original(bitmap);
    if(s){s->original_rc=rc;__atomic_store_n(&s->ready,1,__ATOMIC_RELEASE);}
    return rc;
}
__attribute__((noinline)) static int submit_entry(U a,U b,const U *descriptor,U callback,U argument) {
    U caller=(U)__builtin_return_address(0);
    struct sample *s=caller==base+0x68d21f&&descriptor?reserve(2,caller):0;
    if(s) {
        s->source=descriptor[0];s->target=descriptor[3];
        s->src_size=descriptor[2];s->dst_xy=descriptor[4];s->dst_size=descriptor[5];
    }
    int (*original)(U,U,const U *,U,U)=(void *)hooks.original[1];
    int rc=original(a,b,descriptor,callback,argument);
    if(s){s->original_rc=rc;__atomic_store_n(&s->ready,1,__ATOMIC_RELEASE);}
    return rc;
}
API int IM_SAMPLE_SO_init(void) {
    if(a7c_native_marker.init++)return -1;
    base=(U)&TextRM_loadFont-0x57d271;
    U *u=(void *)(base+0x13d08dc),*b=(void *)(base+0x13d0640);
    U saved_u=__atomic_load_n(u,__ATOMIC_ACQUIRE),saved_b=__atomic_load_n(b,__ATOMIC_ACQUIRE);
    /* ELF symbols are defined locally at pinned offsets. An unresolved entry
     * is PLT0, which requires loader stack metadata and must never be called
     * through the ordinary wrapper ABI. Keep it only for exact restoration. */
    if((saved_u!=base+0x68dc39&&saved_u!=base+0x1076b4)||
       (saved_b!=base+0x68ce03&&saved_b!=base+0x1076b4))return -3;
    a7c_native_marker.prepare_rc=dds_import_prepare(&hooks,u,b,saved_u,saved_b,
        base+0x68dc39,base+0x68ce03,(U)unlock_entry,(U)submit_entry);
    if(a7c_native_marker.prepare_rc)return a7c_native_marker.prepare_rc;
    return a7c_native_marker.install_rc=dds_import_install(&hooks);
}
API int IM_SAMPLE_SO_exit(void) {
    a7c_native_marker.exit++;
    return a7c_native_marker.restore_rc=(int)dds_import_restore(&hooks);
}
API int IM_SAMPLE_SO_sus(void){a7c_native_marker.suspend++;return 0;}
API int IM_SAMPLE_SO_res(void){a7c_native_marker.resume++;return 0;}
API int IM_SAMPLE_SO_inact(void){a7c_native_marker.inactive++;return 0;}
API int IM_SAMPLE_SO_act(void){a7c_native_marker.active++;return 0;}

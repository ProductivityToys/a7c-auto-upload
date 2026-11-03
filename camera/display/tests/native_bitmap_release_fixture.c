/* Offline only. Exercise the actual GRM release wrapper and ref decrement.
 * Synthetic object, real mutex; never reach final destruction or any driver. */
typedef unsigned U;
extern int printf(const char *,...);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern unsigned alarm(unsigned);
static U object[40],vtable[26];
int main(void) {
    alarm(10);
    void *native=dlopen("/lab/libObj.so",1);
    void *thread=dlopen("/lab/libpthread.so.0",1);
    if(!native||!thread)return 1;
    U address=(U)dlsym(native,"TextRM_loadFont");
    int (*initialize)(void *,const void *)=dlsym(thread,"pthread_mutex_init");
    int (*destroy)(void *)=dlsym(thread,"pthread_mutex_destroy");
    if(!address||!initialize||!destroy)return 2;
    U base=address-0x57d271;
    int (*release)(void *)=(void *)(base+0x68dc59);
    vtable[0x64/4]=base+0x6b7765; /* native no-op pre-release method */
    vtable[0x58/4]=base+0x6b76e9; /* native mutex/refcount implementation */
    object[0]=(U)vtable;
    if(initialize(object+0x24/4,0))return 3;
    for(U refs=3;refs>=2;refs--) {
        object[0x14/4]=refs;
        int rc=release(object);
        printf("NATIVE_RELEASE before=%u rc=%d remaining=%u\n",refs,rc,object[0x14/4]);
        if(rc||object[0x14/4]!=refs-1)return 4;
    }
    /* Fixture owns static storage. Never pass the last reference to native free. */
    if(destroy(object+0x24/4))return 5;
    printf("NATIVE_RELEASE_CONTRACT_OK success_does_not_mean_destroyed\n");
    return 0;
}

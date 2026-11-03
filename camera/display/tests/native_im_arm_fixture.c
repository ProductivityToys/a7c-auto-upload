/* OFFLINE ONLY. Map original im code privately; never execute im startup.
 * OSAL is simulated; lookup is synthetic or original IMDB in private memory.
 * The loader, lifecycle bookkeeping,
 * native dispatch, dlopen/dlsym/dlclose and our marker callbacks execute. */
typedef unsigned U;
extern int printf(const char *, ...);
extern int fflush(void *);
extern void _exit(int);
extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern char *dlerror(void);
extern int dlclose(void *);
extern void *malloc(U);
extern void free(void *);
extern void *memcpy(void *,const void *,U);
extern void *mmap(void *, U, int, int, int, U);
extern int mprotect(void *, U, int);
extern int open(const char *, int, ...);
extern int read(int, void *, U);
extern int close(int);
extern unsigned alarm(unsigned);
extern void __clear_cache(void *, void *);
static U counts[5], opens, closes, allocations, dynamic_ids, next_id=0x200;
#ifdef NATIVE_IMDB
static U *entry, *database, baseline[2343];
static void *database_handle;
static void *(*native_lookup)(U,U);
#else
static U entry[11];
#endif
static void *last_handle;
static struct { U id; int count; } semaphores[128];
static U semaphore_count;
static int string_equal(const char *a, const char *b) {
    while (*a && *a==*b) { a++; b++; }
    return *a==*b;
}
void lab_event(U n) { if (n<5) counts[n]++; else _exit(90); }
static void *tracked_malloc(U n) { void *p=malloc(n); if(p) allocations++; return p; }
static void tracked_free(void *p) { if(p) { if(!allocations) _exit(91); allocations--; } free(p); }
static void *tracked_open(const char *p, int flags) {
    opens++; last_handle=dlopen(p,flags); return last_handle;
}
static int tracked_close(void *p) { closes++; return dlclose(p); }
static void *lookup(U id, U mask) {
#ifdef NATIVE_IMDB
    return native_lookup(id,mask);
#else
    return id==(entry[3]&65535) && (entry[2]&mask) ? entry : 0;
#endif
}
static int dynamic_id(U op, U owner, U *out) {
    if(op==0x32 && owner==0x94 && out) {
        U n=semaphore_count++;
        if(n>=128) _exit(92);
        semaphores[n].id=++next_id; semaphores[n].count=1;
        *out=next_id; dynamic_ids++; return 0;
    }
    if(op==0x52 && !owner) {
        U id=(U)out;
        for(U i=0;i<semaphore_count;i++) if(semaphores[i].id==id) {
            if(semaphores[i].count!=1 || !dynamic_ids) _exit(93);
            semaphores[i].id=0; dynamic_ids--; return 0;
        }
    }
    _exit(94); return -1;
}
static int wait_sem(U id, int timeout) {
    (void)timeout;
    for(U i=0;i<semaphore_count;i++) if(semaphores[i].id==id) {
        if(semaphores[i].count!=1) _exit(95);
        semaphores[i].count=0; return 0;
    }
    _exit(96); return -1;
}
static int signal_sem(U id) {
    for(U i=0;i<semaphore_count;i++) if(semaphores[i].id==id) {
        if(semaphores[i].count!=0) _exit(97);
        semaphores[i].count=1; return 0;
    }
    _exit(98); return -1;
}
static void unexpected_sleep(void) { printf("UNEXPECTED_RETRY_LOOP\n"); fflush(0); _exit(99); }
#include "im_imports.h"
static void *resolve(const char *s, void *fallback) {
    if(string_equal(s,"malloc")) return tracked_malloc;
    if(string_equal(s,"free")) return tracked_free;
    if(string_equal(s,"dlopen")) return tracked_open;
    if(string_equal(s,"dlclose")) return tracked_close;
    if(string_equal(s,"dlsym")) return dlsym;
    if(string_equal(s,"dlerror")) return dlerror;
    if(string_equal(s,"IMDB_find_entry")) return lookup;
    if(string_equal(s,"osal_dynamic_id")) return dynamic_id;
    if(string_equal(s,"osal_wai_sem_tmo")) return wait_sem;
    if(string_equal(s,"osal_sig_sem")) return signal_sem;
    if(string_equal(s,"usleep")) return unexpected_sleep;
    return fallback;
}
static void init_descriptor(const char *path, const char *init) {
    for(U i=0;i<11;i++) entry[i]=0;
    entry[0]=0x20000003; entry[1]=entry[2]=1; entry[3]=0x7ef;
    entry[4]=(U)path; entry[5]=(U)init; entry[6]=(U)"a7c_module_exit";
}
static int dispatch(U op, U owner) {
    U message[4]={op,0x7ef,3,owner};
    ((void (*)(void *))0x97ed)(message);
    return (int)message[1];
}
static int checkpoint(const char *name, int rc, int expected, U init, U exit, U nodes) {
    U head=*(U *)0x15514;
    int ok=rc==expected && counts[2]==init && counts[3]==exit && (!!head)==(!!nodes);
    printf("CASE %s rc=%d expected=%d init=%u exit=%u ctor=%u dtor=%u heap=%u sem=%u head=%u ok=%d\n",
           name,rc,expected,counts[2],counts[3],counts[1],counts[4],allocations,dynamic_ids,!!head,ok);
    fflush(0); return ok;
}
int main(void) {
    alarm(10);
    printf("STAGE entered_fixture\n"); fflush(0);
#ifdef NATIVE_IMDB
    database_handle=dlopen("/probe/libIMDB.so",2);
    if(!database_handle) {printf("IMDB_OPEN_FAILED %s\n",dlerror());return 30;}
    database=dlsym(database_handle,"imdb_raw");
    native_lookup=dlsym(database_handle,"IMDB_find_entry");
    if(!database || !native_lookup) return 31;
    for(U i=0;i<2343;i++) baseline[i]=database[i];
    entry=native_lookup(0x7ef,1);
    if(entry!=database+33+208*11 || entry[0]!=0x20000003 ||
       !string_equal((char *)entry[4],"libIMSample.so") ||
       database[33+209*11]!=40 || native_lookup(0x7ef,0xffffffffU)) return 32;
    printf("NATIVE_IMDB original_lookup=1 entries=209 selected_id=2031 original_module_not_executed=1\n");
#endif
    /* Fixed low mapping matches im's ET_EXEC addresses; fixture is linked at
       0x1000000 (also avoiding the directly invoked loader at 0x400000).
       A differing hint result aborts; do not overwrite other maps. */
    void *map=mmap((void *)0x8000,0xe000,7,0x22,-1,0);
    if(map!=(void *)0x8000) { printf("MAPPING_FAILED %p\n",map); return 2; }
    printf("STAGE mapped\n"); fflush(0);
    int fd=open("/probe/im-flat.bin",0);
    if(fd<0) return 3;
    U got=0;
    while(got<0xe000) { int n=read(fd,(char *)map+got,0xe000-got); if(n<=0) return 4; got+=(U)n; }
    close(fd);
    printf("STAGE image_copied\n"); fflush(0);
    for(U i=0;i<sizeof(imports)/sizeof(imports[0]);i++)
        *(U *)imports[i].address=(U)resolve(imports[i].name,imports[i].fallback);
    __clear_cache(map,(char *)map+0xe000);
    printf("STAGE imports_bound\n"); fflush(0);
    if(mprotect(map,0x6000,5)) return 5; /* original text/rodata stays unmodified */
    *(U *)0x154e4=2; /* lab dlopen RTLD_NOW */
    *(U *)0x154ec=1; /* lab target mask */
    *(U *)0x15424=0x13579bdf; /* synthetic identity state, never camera state */
    U identity[4]={0x9400e1,0,0,0xdeadbeef};
    ((void (*)(void *))0x97ed)(identity);
    if(identity[0]!=0x9400e1 || identity[1]!=0x12345678 ||
       identity[2]!=0x13579bdf || identity[3]!=0xdeadbeef ||
       allocations || dynamic_ids || opens || closes) return 6;
    printf("CASE identity magic=%08x state=%08x no_module_side_effects=1\n",identity[1],identity[2]);
    semaphores[0].id=0x9401c3; semaphores[0].count=1; semaphore_count=1;
    init_descriptor("/probe/marker.so","a7c_module_init");
    printf("STAGE dispatch\n"); fflush(0);
    if(!checkpoint("first_load",dispatch(0x940021,0x111),0,1,0,1)) return 10;
    if(!checkpoint("same_owner_load",dispatch(0x940021,0x111),0,1,0,1)) return 11;
    if(!checkpoint("second_owner_load",dispatch(0x940021,0x222),0,1,0,1)) return 12;
    if(!checkpoint("wrong_owner_unload",dispatch(0x940022,0x333),-9,1,0,1)) return 13;
    if(!checkpoint("first_reference_release",dispatch(0x940022,0x111),0,1,0,1)) return 14;
    if(!checkpoint("first_owner_release",dispatch(0x940022,0x111),0,1,0,1)) return 15;
    if(!checkpoint("last_owner_release",dispatch(0x940022,0x222),0,1,1,0)) return 16;
    if(allocations || dynamic_ids || opens!=1 || closes || counts[4]) return 17;
    printf("OBSERVATION init_rc=-17 exit_rc=-19 ignored=1 native_dlclose=0 library_still_loaded=1\n");
    if(!checkpoint("already_unloaded",dispatch(0x940022,0x222),-9,1,1,0)) return 18;
    /* Only the isolated fixture closes the retained dlopen handle. */
    if(dlclose(last_handle) || counts[4]!=1) return 19;
    init_descriptor("/probe/missing.so","a7c_module_init");
    if(!checkpoint("missing_library",dispatch(0x940021,0x111),-1,1,1,0)) return 20;
    init_descriptor("/probe/marker.so","missing_symbol");
    if(!checkpoint("missing_init_symbol",dispatch(0x940021,0x111),-2,1,1,0)) return 21;
    if(allocations || dynamic_ids || closes!=1 || counts[1]!=2 || counts[4]!=2) return 22;
    entry[2]=2;
    if(!checkpoint("target_mask_reject",dispatch(0x940021,0x111),-4,1,1,0)) return 23;
#ifdef NATIVE_IMDB
    /* No marker owner or loader bookkeeping may survive restoration. This is
       private memory only; this does not establish safe live table ownership. */
    if(*(U *)0x15514 || allocations || dynamic_ids) return 33;
    for(U i=0;i<2343;i++) {
        U start=33+208*11;
        if((i<start || i>=start+11) && database[i]!=baseline[i]) return 34;
    }
    for(U i=0;i<11;i++) entry[i]=baseline[33+208*11+i];
    for(U i=0;i<2343;i++) if(database[i]!=baseline[i]) return 35;
    if(native_lookup(0x7ef,1)!=entry ||
       !string_equal((char *)entry[4],"libIMSample.so")) return 36;
    printf("NATIVE_IMDB_RESTORED all_words=2343\n");
    /* Second experiment: keep the real descriptor and callback names exactly
       intact; only change its private copy of the 15-byte library pathname.
       The original sample library is never executed. Not a camera patcher. */
    char *path=(char *)entry[4];
    char saved_path[15], trial_path[15]="/probe/nt.so";
    U page=(U)path&~4095U;
    memcpy(saved_path,path,15);
    if(mprotect((void *)page,4096,3))return 38;
    memcpy(path,trial_path,15);
    if(mprotect((void *)page,4096,5))return 39;
#ifdef STANDALONE_MARKER
    if(!checkpoint("standalone_load",dispatch(0x940021,0x444),0,1,1,1))return 40;
    volatile U *marker=dlsym(last_handle,"a7c_native_marker");
    if(!marker || marker[0]!=0x41374d31 || marker[1]!=1 || marker[2]!=1 || marker[3])return 41;
    if(!checkpoint("standalone_exit",dispatch(0x940022,0x444),0,1,1,0))return 42;
    if(marker[2]!=1 || marker[3]!=1)return 47;
    for(U i=4;i<8;i++)if(marker[i])return 48;
    printf("STANDALONE_MARKER_OK init=1 exit=1 other_callbacks=0\n");
    if(allocations || dynamic_ids || dlclose(last_handle) || counts[4]!=2)return 49;
#else
    if(!checkpoint("path_only_load",dispatch(0x940021,0x444),0,2,1,1))return 40;
    if(!checkpoint("path_only_exit",dispatch(0x940022,0x444),0,2,2,0))return 41;
    if(allocations || dynamic_ids || dlclose(last_handle) || counts[4]!=3)return 42;
#endif
    if(mprotect((void *)page,4096,3))return 43;
    memcpy(path,saved_path,15);
    if(mprotect((void *)page,4096,5))return 44;
    for(U i=0;i<2343;i++)if(database[i]!=baseline[i])return 45;
    if(!string_equal(path,"libIMSample.so"))return 46;
    printf("NATIVE_IMDB_PATH_ONLY_OK cases=2 descriptor_unchanged=1 path_bytes_restored=15\n");
    if(dlclose(database_handle)) return 37;
#endif
    printf("A7C_NATIVE_IM_LAB_OK 12\n");
    return 0;
}

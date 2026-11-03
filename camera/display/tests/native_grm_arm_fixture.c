/* OFFLINE ONLY: run original wrappers against simulated bitmap/driver edges.
 * Never load this fixture or its patched library into a camera process. */
extern int printf(const char *, ...);
extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern char *dlerror(void);
extern int mprotect(void *, unsigned, int);
extern void __clear_cache(void *, void *);
extern unsigned alarm(unsigned);
typedef unsigned U;
typedef unsigned short H;
struct rect { H x, y, w, h; };
struct bitmap { struct rect rect; };
static struct bitmap target = {{0, 0, 640, 480}};
static unsigned char descriptor[80];
static char events[32];
static U event_count, submissions;
static int acquire_rc, submit_rc, release_rc, bad_call;
static void event(char c) {
    if (event_count < sizeof(events)-1) events[event_count++] = c;
    else bad_call = 1;
    events[event_count] = 0;
}
static void lock(void) { event('L'); }
static void unlock(void) { event('U'); }
static int acquire(void **out) { event('A'); *out = &target; return acquire_rc; }
static int retain(void *p) { event('R'); if (p != &target) bad_call = 1; return 0; }
static int release(void *p) { event('D'); if (p != &target) bad_call = 1; return release_rc; }
static int rectangle(struct bitmap *p, struct rect **out) {
    event('G'); *out = &p->rect; return 0;
}
static int submit(U a, U b, const unsigned char *p, U c, U d) {
    event('B'); submissions++;
    if (a || b || c || d) bad_call = 1;
    for (U i = 0; i < sizeof(descriptor); i++) descriptor[i] = p[i];
    return submit_rc;
}
/* Replace only simulated boundary entries in private, offline mapped pages.
 * ldr.w pc,[pc,#0 or #2] supports both Thumb halfword alignments. */
static int replace(U address, void *callback) {
    address &= ~1U;
    U page = address & ~4095U;
    if (mprotect((void *)page, 8192, 7)) return 1;
    H *code = (H *)address;
    code[0] = 0xf8df; code[1] = 0xf000 | (address & 2);
    unsigned char *literal = (void *)(address + 4);
    U dest = (U)callback;
    for (U i = 0; i < 4; i++) literal[i] = dest >> (8*i);
    __clear_cache((void *)address, (void *)(address+8));
    return mprotect((void *)page, 8192, 5) != 0;
}
static void reset(int a, int s, int r) {
    event_count = submissions = bad_call = 0; events[0] = 0;
    acquire_rc = a; submit_rc = s; release_rc = r;
    for (U i = 0; i < sizeof(descriptor); i++) descriptor[i] = 0;
}
static int equal(const void *a, const void *b, U n) {
    const unsigned char *x=a, *y=b;
    for (U i=0; i<n; i++) if (x[i]!=y[i]) return 0;
    return 1;
}
static int verify(struct bitmap *source, struct rect *src, struct rect *dst,
                  const char *order, U order_length) {
    U words[20] = {0};
    unsigned char *expected = (void *)words;
    words[0] = (U)source; words[3] = (U)&target;
    words[8] = 1; expected[36] = 255;
    words[15] = words[16] = 0x3f800000;
    const unsigned char *rects[] = {(void *)src, (void *)dst, (void *)&target.rect};
    const U offsets[] = {4, 16, 24};
    for (U j=0; j<3; j++) for (U i=0; i<8; i++) expected[offsets[j]+i]=rects[j][i];
    return !bad_call && submissions == 1 && equal(expected, descriptor, 80) &&
           event_count == order_length && equal(events, order, order_length);
}
int main(void) {
    alarm(10);
    void *lib = dlopen("/lab/libObj.so", 1);
    if (!lib) { printf("LOAD_ERROR %s\n", dlerror()); return 2; }
    void *font = dlsym(lib, "TextRM_loadFont");
    void *get_rect = dlsym(lib, "GRM_bitmapGetSubRectangle");
    void *blit = dlsym(lib, "GRM_gpermRectblit");
    if (!font || !get_rect || !blit) return 3;
    U base = (U)font - 0x57d271;
    if (replace(base+0x75ccf4, lock) || replace(base+0x75cce4, unlock) ||
        replace(base+0x75cca4, acquire) || replace(base+0x68dc48, retain) ||
        replace(base+0x68dc58, release) || replace((U)get_rect, rectangle) ||
        replace((U)blit, submit)) return 4;
    int (*overlay)(void *, void *, void *) = (void *)(base+0x68d13d);
    int (*dds)(U, U, void *, void *) = (void *)(base+0x7db519);
    struct bitmap source = {{0, 0, 71, 20}};
    struct rect dst = {550, 400, 71, 20};
    reset(0,0,0);
    int rc = overlay(&source, &source.rect, &dst);
    if (rc || !verify(&source,&source.rect,&dst,"LARUGBD",7)) return 10;
    printf("CASE native_size source=71x20 destination=71x20 clip=640x480 order=%s rc=%d\n",events,rc);
    /* Execute original DDS wrapper as the negative control, not a Python model. */
    source.rect.w=288; source.rect.h=32; dst.w=576; dst.h=192;
    reset(0,0,0);
    rc=dds(0,0,&source,&dst);
    if (rc || !verify(&source,&source.rect,&dst,"GLARUGBD",8)) return 11;
    printf("CASE dds_scale source=288x32 destination=576x192 order=%s rc=%d\n",events,rc);
    source.rect.w=dst.w=71; source.rect.h=dst.h=20;
    reset(0,-23,0);
    rc=overlay(&source,&source.rect,&dst);
    if (rc || !verify(&source,&source.rect,&dst,"LARUGBD",7)) return 12;
    printf("CASE submit_failure injected=-23 wrapper_rc=%d swallowed=1 release=1\n",rc);
    reset(0,0,-9);
    rc=overlay(&source,&source.rect,&dst);
    if (rc!=-9 || !verify(&source,&source.rect,&dst,"LARUGBD",7)) return 13;
    printf("CASE release_failure injected=-9 wrapper_rc=%d\n",rc);
    reset(-7,0,0);
    rc=overlay(&source,&source.rect,&dst);
    if (!rc || bad_call || submissions || event_count!=3 || !equal(events,"LAU",3)) return 14;
    printf("CASE target_failure injected=-7 wrapper_rc=%d order=%s submissions=%u\n",rc,events,submissions);
    printf("A7C_NATIVE_GRM_BOUNDARY_OK 5\n");
    return 0;
}

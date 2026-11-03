/* Offline ARM font lab only; never install on a camera. */
extern int printf(const char *, ...);
extern int snprintf(char *, unsigned, const char *, ...);
extern int fflush(void *);
extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern char *dlerror(void);
extern unsigned alarm(unsigned);
extern void *calloc(unsigned, unsigned);
extern void free(void *);
typedef unsigned U;
typedef unsigned short H;
struct dimensions { H width, height; U stride; };
static int (*create_text)(const char *, U, U, void *, short, U *);
static int (*get_bounds)(U, void *);
static int (*draw_text)(U, void *, void *, U *);
static int (*delete_text)(U);
static void stage(const char *s, int rc) { printf("%s %d\n", s, rc); fflush(0); }
static int render(U font, U size, U progress, int emit) {
    char label[16]; snprintf(label, sizeof(label), "UD %u%%", progress);
    U attributes[12] = {0};
    attributes[0] = font; attributes[1] = 1;
    ((H *)attributes)[4] = size; ((H *)attributes)[5] = size;
    attributes[3] = 1; attributes[4] = 0xffffffff; /* white, transparent background */
    U text = 0;
    int rc = create_text(label, 0, 0x8ff, attributes, 0, &text);
    if (rc) { stage("CREATE_FAILED", rc); return 10; }
    struct dimensions dim = {0};
    rc = get_bounds(text, &dim);
    if (rc || !dim.width || dim.width > (size == 20 ? 78 : 128) ||
        dim.height != size || dim.stride != dim.width * 2U) {
        stage("DIMENSIONS_FAILED", rc); delete_text(text); return 11;
    }
    U bytes = dim.stride * dim.height;
    unsigned char *allocation = calloc(bytes + 128, 1);
    if (!allocation) { delete_text(text); return 12; }
    unsigned char *pixels = allocation + 64;
    for (U i = 0; i < 64; i++) allocation[i] = pixels[bytes + i] = 0x5a;
    U changed = 0;
    rc = draw_text(text, &dim, pixels, &changed);
    int guard_ok = 1; U nonzero = 0, intermediate_alpha = 0, transparent = 0;
    for (U i = 0; i < 64; i++) if (allocation[i] != 0x5a || pixels[bytes+i] != 0x5a) guard_ok = 0;
    for (U i = 0; i < bytes; i += 2) {
        U value = pixels[i] | ((U)pixels[i+1] << 8), a = value & 15;
        if (value) nonzero++;
        if (a && a < 15) intermediate_alpha++;
        if (!value) transparent++;
    }
    int good = !rc && guard_ok && nonzero && intermediate_alpha && transparent;
    printf("CASE size=%u progress=%u width=%u height=%u stride=%u rc=%d guard=%d ink=%u aa=%u transparent=%u\n",
           size, progress, dim.width, dim.height, dim.stride, rc, guard_ok, nonzero, intermediate_alpha, transparent);
    if (good && emit) {
        printf("PIXELS_%u ", size);
        for (U i = 0; i < bytes; i++) printf("%02x", pixels[i]);
        printf("\n");
    }
    fflush(0); free(allocation);
    int cleanup = delete_text(text);
    if (cleanup) stage("DELETE_FAILED", cleanup);
    return good && !cleanup ? 0 : 13;
}
int main(void) {
    alarm(15);
    void *handle = dlopen("/lab/libObj.so", 1);
    if (!handle) { printf("LOAD_ERROR %s\n", dlerror()); return 2; }
    stage("LOADED", 0);
    int (*load_font)(const char *, U *) = dlsym(handle, "TextRM_loadFont");
    if (!load_font) return 3;
    U base = (U)load_font - 0x57d271;
    int (*init)(void) = (void *)(base + 0x57d8b9);
    int rc = init(); stage("INIT", rc); if (rc) return 4;
    U font = 0; rc = load_font("FONT_UNIVERS", &font); stage("FONT", rc); if (rc) return 5;
    create_text = dlsym(handle, "TextRM_createText");
    get_bounds = dlsym(handle, "TextRM_getBounds");
    draw_text = dlsym(handle, "TextRM_drawText");
    delete_text = dlsym(handle, "TextRM_deleteText");
    int (*unload_font)(U) = dlsym(handle, "TextRM_unloadFont");
    if (!create_text || !get_bounds || !draw_text || !delete_text || !unload_font) return 6;
    for (U i = 0; i < 100 && !rc; i++) rc = render(font, 20, i, i == 42);
    if (!rc) rc = render(font, 24, 42, 1);
    int cleanup = unload_font(font); stage("UNLOAD", cleanup);
    if (!rc && !cleanup) stage("A7C_NATIVE_TEXT_LAB_OK", 101);
    return rc ? rc : cleanup;
}

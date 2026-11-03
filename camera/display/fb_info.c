/* Experimental diagnostic, ILCE-7C 2.00 ARM EABI only.
 * Only O_RDONLY opens and FBIOGET_* queries; no mmap, pixel read/write,
 * mode change, blanking, panning, allocation or native UI calls.
 * Linux framebuffer ABI reference:
 * https://github.com/torvalds/linux/blob/v2.6.35/include/linux/fb.h
 * A successful query does not establish that independent drawing is safe.
 */
typedef unsigned int u32;
extern int open(const char *, int, ...), close(int), ioctl(int, unsigned long, ...);
extern int printf(const char *, ...), fflush(void *), *__errno_location(void);
extern unsigned alarm(unsigned);
_Static_assert(sizeof(u32) == 4 && sizeof(unsigned long) == 4, "ARM32 ABI required");

/* Oversized, aligned, zeroed buffers allow bounded inspection without
 * assuming the vendor implements the complete standard structure. */
static u32 fixed[128], variable[128];

int main(void) {
    const char *paths[] = {"/dev/fb0", "/dev/fb1"};
    alarm(8);
    printf("A7C_FB_INFO_V1 readonly=1\n"); fflush(0);
    for (unsigned i = 0; i != 2; ++i) {
        int fd = open(paths[i], 0); /* O_RDONLY */
        int err = fd < 0 ? *__errno_location() : 0;
        printf("DEVICE=%s open=%d errno=%d\n", paths[i], fd >= 0, err); fflush(0);
        if (fd < 0) continue;
        for (unsigned j = 0; j != 128; ++j) fixed[j] = variable[j] = 0;
        int fr = ioctl(fd, 0x4602UL, fixed); /* FBIOGET_FSCREENINFO */
        err = fr < 0 ? *__errno_location() : 0;
        printf("FIX rc=%d errno=%d\n", fr, err);
        if (!fr) {
            /* ARM32 fb_fix_screeninfo: bytes 20..32 and 44. */
            printf("FIX smem_len=%u type=%u type_aux=%u visual=%u line_length=%u\n",
                   fixed[5], fixed[6], fixed[7], fixed[8], fixed[11]);
        }
        fflush(0);
        int vr = ioctl(fd, 0x4600UL, variable); /* FBIOGET_VSCREENINFO */
        err = vr < 0 ? *__errno_location() : 0;
        printf("VAR rc=%d errno=%d\n", vr, err);
        if (!vr) {
            printf("VAR x=%u y=%u virtual_x=%u virtual_y=%u offset_x=%u offset_y=%u bpp=%u grayscale=%u\n",
                   variable[0], variable[1], variable[2], variable[3],
                   variable[4], variable[5], variable[6], variable[7]);
            printf("COLOR red=%u:%u:%u green=%u:%u:%u blue=%u:%u:%u alpha=%u:%u:%u\n",
                   variable[8], variable[9], variable[10],
                   variable[11], variable[12], variable[13],
                   variable[14], variable[15], variable[16],
                   variable[17], variable[18], variable[19]);
        }
        int cr = close(fd);
        printf("CLOSE rc=%d\n", cr); fflush(0);
    }
    printf("A7C_FB_INFO_END\n"); fflush(0);
    return 0;
}

/* One-shot CPU-state observation at the already tested gain boundary.
 * No native graphics calls, allocation, logs or pixel access. The callback
 * runs after scene/post and before original gain/present, not inside post. */
#ifndef A7C_GAIN_SCOPE_H
#define A7C_GAIN_SCOPE_H
struct gain_scope { unsigned outer,delegate,active,selector,state_active,
    rectangles,vertices,indices; int rc; };
static int gain_scope_read(unsigned base,struct gain_scope *s) {
    volatile unsigned *global=(void *)(base+0x1453918);
    unsigned outer=*global;
    if(!outer||*(volatile unsigned *)outer!=base+0x13b68c0)return s->rc=-1;
    unsigned delegate=*(volatile unsigned *)(outer+0x10);
    if(!delegate||*(volatile unsigned *)delegate!=base+0x13b6648)return s->rc=-2;
    s->outer=outer;s->delegate=delegate;
    s->active=*(volatile unsigned char *)(outer+0x404)&1;
    s->selector=*(volatile unsigned *)(outer+0x348);
    s->state_active=*(volatile unsigned char *)(delegate+0x28+0x7c);
    s->rectangles=*(volatile unsigned short *)(outer+0x2c4+0x62);
    s->vertices=*(volatile unsigned *)(outer+0x2c4+0x4c);
    s->indices=*(volatile unsigned *)(outer+0x2c4+0x58);
    return s->rc=*global==outer&&*(volatile unsigned *)(outer+0x10)==delegate?0:-3;
}
#endif

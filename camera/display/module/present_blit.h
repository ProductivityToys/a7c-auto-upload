#ifndef A7C_PRESENT_BLIT_H
#define A7C_PRESENT_BLIT_H
/* Fixed 1:1 RGBA4444 label into an empty 78x20 region only. No GPU or native
 * calls. A preflight overlap refuses the WHOLE write; no background restore.
 * Caller establishes the current front, mode and same-thread presentation. */
static int present_blit(volatile unsigned short *pixels,const unsigned short *glyph,
                        unsigned *before,unsigned *after,unsigned *matched) {
    *before=*after=*matched=0;
    for(unsigned y=0;y<20;y++)for(unsigned x=0;x<78;x++)
        if(pixels[(432+y)*640+562+x])(*before)++;
    if(*before)return -3;
    for(unsigned y=0;y<20;y++)for(unsigned x=0;x<71;x++)
        pixels[(432+y)*640+562+x]=glyph[y*71+x];
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    for(unsigned y=0;y<20;y++)for(unsigned x=0;x<78;x++) {
        unsigned short want=x<71?glyph[y*71+x]:0;
        unsigned short got=pixels[(432+y)*640+562+x];
        if(got)(*after)++;
        if(got==want)(*matched)++;
    }
    return *matched==78*20?0:-4;
}
#endif

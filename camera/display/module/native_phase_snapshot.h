/* Pinned ILCE-7C 2.00 diagnostic state; read only, never enables tracing.
 * 0x898380 writes timestamp + fixed 16-byte label to slot zero at +12.
 * These are stage ENTRY records, not evidence of GPU completion. */
extern void *mmap64(void *,unsigned,int,int,int,long long);
extern int munmap(void *,unsigned);
static int native_phase_read(U pointer,U *out){
    if(!rd(pointer,out,36))return 0;
    /* Only the observed slot, in a VMA verified by get_maps. /proc/iomem
     * confirms 0x03103000 is System RAM, not a peripheral register aperture.
     * Map one page read-only and copy exactly nine words; no cache operations. */
    if(!phase_mapping||pointer!=phase_mapping+0x390)return -1;
    int fd=open("/dev/mem",0);if(fd<0)return -1;
    void *mapped=mmap64(0,4096,1,1,fd,0x03103000LL);
    if(mapped==(void *)-1){close(fd);return -1;}
    const volatile U *words=(const volatile U *)((char *)mapped+0x390);
    for(U n=0;n<9;n++)out[n]=words[n];
    int ur=munmap(mapped,4096),cr=close(fd);
    return ur||cr?-1:0;
}
static int native_phase_snapshot(U base) {
    U magic, pointer, again, before[9], after[9], pending[2], view, graphics;
    const unsigned char expected[8]={0x2d,0xe9,0xf0,0x41,0x82,0xb0,0x1a,0x4e};
    unsigned char code[8];
    if(rd(base,&magic,4)||magic!=0x464c457f||
       rd(base+0x898380,code,8)||memcmp(code,expected,8)||
       rd(0x1550c,pending,sizeof pending)||rd(base+0x1488e84,&pointer,4))return 82;
    printf("NATIVE_PHASE pending_inact=%u pending_act=%u trace=%08x\n",pending[0],pending[1],pointer);
    if(!pointer)printf("NATIVE_PHASE_TRACE disabled=1\n");
    else {
        int stable=0;
        for(U attempt=0;attempt<3;attempt++) {
            if(native_phase_read(pointer,before)||native_phase_read(pointer,after)||
               rd(base+0x1488e84,&again,4))return 83;
            if(pointer==again&&!memcmp(before,after,sizeof before)){stable=1;break;}
        }
        char label[17];
        for(U n=0;n<16;n++){
            unsigned char c=((unsigned char *)(before+5))[n];
            label[n]=(c>=32&&c<=126)?(char)c:'.';
        }
        label[16]=0;
        printf("NATIVE_PHASE_TRACE stable=%u header=%08x:%08x:%08x timestamp=%08x:%08x label=%s\n",
               stable,before[0],before[1],before[2],before[3],before[4],label);
    }
    /* One verified ViewManager -> Graphics relation; no arbitrary walk. */
    if(rd(base+0x1488fdc,&view,4))return 84;
    if(view&& !rd(view+0x14,&graphics,4)&&graphics){
        U skip;
        if(!rd(graphics+0x38,&skip,4))printf("NATIVE_PHASE_GRAPHICS view=%08x graphics=%08x skip=%u\n",view,graphics,skip);
    }
    printf("NATIVE_PHASE_END read_only=1 stage_entry_not_completion=1\n");
    return 0;
}
/* A ten-second alarm is owned by the caller. A bounded burst samples existing
 * diagnostic RAM, without calling into IM or touching graphics. */
extern int usleep(unsigned);
static int native_phase_burst(U base){
    int rc=native_phase_snapshot(base);if(rc)return rc;
    U pointer;
    if(rd(base+0x1488e84,&pointer,4)||!phase_mapping||pointer!=phase_mapping+0x390)return 85;
    int fd=open("/dev/mem",0);if(fd<0)return 85;
    void *mapped=mmap64(0,4096,1,1,fd,0x03103000LL);
    if(mapped==(void *)-1){close(fd);return 85;}
    const volatile U *words=(const volatile U *)((char *)mapped+0x390);
    U previous[6]={0},stable=0,changed=0,ticks=0,printed=0,samples=0;
    for(U n=0;n<400;n++){
        U current[6],again[6];
        for(U j=0;j<6;j++)current[j]=words[j+3];
        for(U j=0;j<6;j++)again[j]=words[j+3];
        samples++;
        if(!memcmp(current,again,sizeof current)){
            stable++;
            if(current[0]!=previous[0]||current[1]!=previous[1])ticks++;
            if(!n||memcmp(current+2,previous+2,16)){
                changed++;
                if(printed<64){
                    char label[17];
                    for(U j=0;j<16;j++){
                        unsigned char c=((unsigned char *)(current+2))[j];
                        label[j]=(c>=32&&c<=126)?(char)c:'.';
                    }
                    label[16]=0;
                    printf("NATIVE_BURST sample=%u timestamp=%08x:%08x label=%s\n",n,current[0],current[1],label);
                    printed++;
                }
            }
            for(U j=0;j<6;j++)previous[j]=current[j];
        }
        if(!(n%100)){
            U check;
            if(rd(base+0x1488e84,&check,4)||check!=pointer){rc=85;break;}
        }
        if(usleep(1000)){rc=85;break;}
    }
    int ur=munmap(mapped,4096),cr=close(fd);
    printf("NATIVE_BURST_END samples=%u stable=%u timestamp_changes=%u label_changes=%u printed=%u unmap=%d close=%d rc=%d\n",
           samples,stable,ticks,changed,printed,ur,cr,rc);
    return rc?rc:(ur||cr?85:0);
}

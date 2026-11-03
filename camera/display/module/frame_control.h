/* External short-window controller for the fixed 2.00 native-font trial.
 * Included by probe.c. Read-only physical aperture, fixed RAM evidence paths.
 * Exit uses native full redraw, never a saved pixel write into another page. */
extern void *mmap64(void *,unsigned,int,int,int,long long);
extern int munmap(void *,unsigned),execv(const char *,char *const *);
#ifdef RECT_SERVICE_TRIAL
#define FRAME_DIR "/setting/a7c-debug/ram/dds-once/native-service/"
#elif defined(RECT_UPLOAD_TRIAL)
#define FRAME_DIR "/setting/a7c-debug/ram/dds-once/native-rect-v18/"
#elif defined(RECT_SERIES_TRIAL)
#define FRAME_DIR "/setting/a7c-debug/ram/dds-once/native-rect-v17/"
#elif defined(RECT_TRIAL)
#define FRAME_DIR "/setting/a7c-debug/ram/dds-once/native-rect-v16/"
#elif defined(PRESENT_TRIAL)
#define FRAME_DIR "/setting/a7c-debug/ram/native-present-v12/"
#else
#define FRAME_DIR "/setting/a7c-debug/ram/native-frame-v9/"
#endif
#define FRAME_REDRAW "/setting/a7c-debug/ram/dds-once/redraw"
static U frame_base,frame_bitmap,frame_physical;
static unsigned char frame_pixels[614400];
static int frame_mapping(int pid,U *base,U pixels) {
    char name[64],data[262144];
    snprintf(name,sizeof name,"/proc/%d/maps",pid);int f=open(name,0);if(f<0)return -1;
    U used=0;int n;
    while(used<sizeof data-1&&(n=read(f,data+used,sizeof data-1-used))>0)used+=(U)n;
    close(f);if(used==sizeof data-1)return -1;data[used]=0;
    U found=0;char *line=data;*base=0;
    while(*line) {
        char *end=line;while(*end&&*end!='\n')end++;char next=*end;*end=0;
        U lo,hi,offset;char flags[8],path[128];
        if(sscanf(line,"%x-%x %7s %x %*s %*s %127s",&lo,&hi,flags,&offset,path)==5) {
            if(!offset&&!strcmp(path,"/usr/lib/libObj.so"))*base=lo;
            int backing=!strcmp(path,"/dev/mem")&&offset==0xfe33a000&&offset==frame_physical;
#ifdef RECT_SERVICE_TRIAL
            /* Observed native double-buffer bitmap: exact /dev/stream VMA,
             * descriptor physical address and 600 KiB size must all agree.
             * Only ordinary RAM is accepted, never arbitrary MMIO. */
            backing|=!strcmp(path,"/dev/stream")&&offset==frame_physical&&
                     offset>=0x20000000U&&offset<=0x3ff69000U&&!(offset&4095);
#endif
            if(!strcmp(flags,"rw-s")&&backing&&
               lo==pixels&&hi-lo==sizeof frame_pixels)found++;
        }
        if(!next)break;line=end+1;
    }
    return !*base||(pixels&&found!=1)?-1:0;
}
/* Descriptor-only diagnosis shares capture's checks; it never maps pixels. */
static int frame_source(int pid,U *manager) {
    U b=0,obj[32],desc[16];const char *stage="mapping";
    if(frame_mapping(pid,&b,0)||b!=frame_base)goto rejected;
    stage="manager-read";if(rd(b+0x1453df0,manager,64*sizeof(U)))goto rejected;
    printf("FRAME_SOURCE active=%u front=%08x\n",manager[0x58/4],manager[0x8c/4]);
    stage="manager-state";if(manager[0x58/4]!=1||!manager[0x8c/4])goto rejected;
    stage="object-read";if(rd(manager[0x8c/4],obj,sizeof obj))goto rejected;
    printf("FRAME_SOURCE vtable=%08x expected=%08x descriptor=%08x pixels=%08x\n",obj[0],b+0x13b1f50,obj[1],obj[2]);
    stage="object-type";if(obj[0]!=b+0x13b1f50||!obj[1])goto rejected;
    stage="descriptor-read";if(rd(obj[1],desc,sizeof desc))goto rejected;
    const unsigned short *h=(const void *)desc;
    printf("FRAME_SOURCE size=%ux%u backing=%ux%u kind=%u physical=%08x\n",h[8],h[9],h[12],h[13],desc[7],desc[9]);
    stage="descriptor-format";
    if(h[8]!=640||h[9]!=480||h[12]!=640||h[13]!=480||desc[7]!=1)goto rejected;
    if(desc[9]!=0xfe33a000){
#ifdef RECT_SERVICE_TRIAL
        if(desc[9]<0x20000000U||desc[9]>0x3ff69000U||(desc[9]&4095))goto rejected;
#else
        goto rejected;
#endif
    }
    frame_physical=desc[9];
    stage="pixel-mapping";if(frame_mapping(pid,&b,obj[2])||b!=frame_base)goto rejected;
    printf("FRAME_SOURCE_OK\n");fflush(0);return 0;
rejected:
    printf("FRAME_SOURCE_REJECT stage=%s base=%08x expected=%08x\n",stage,b,frame_base);fflush(0);return 87;
}
static int frame_snapshot(int pid,const char *name,int empty) {
    U b=frame_base,manager[64],again[64],life[7];unsigned char slots[208];
    int source=frame_source(pid,manager);if(source)return source;
    if(empty) {
        if(rd(b+0x145aac8,life,sizeof life)||rd(b+0x145aae4,slots,sizeof slots)||
           life[0]!=b+0x13b5238||life[2]!=b+0x13b5288||life[5]!=1||
           !life[3]||life[3]>=512||life[4]>1||slots[204])return 88;
        for(U i=0;i<8;i++) {
            U word;memcpy(&word,slots+i*24+12,4);
            if(slots[i*24+8]||word||slots[i*24+18])return 88;
        }
    }
    int f=open("/dev/mem",0);if(f<0)return 89;
    void *p=mmap64(0,sizeof frame_pixels,1,1,f,(long long)frame_physical);
    if(p==(void *)-1){close(f);return 89;}
    for(U i=0;i<sizeof frame_pixels;i++)frame_pixels[i]=((const volatile unsigned char *)p)[i];
    int unmap=munmap(p,sizeof frame_pixels),closed=close(f);
    if(unmap||closed||rd(b+0x1453df0,again,sizeof again)||again[0x8c/4]!=manager[0x8c/4])return 89;
    U ink=0;
    #ifdef RECT_SERVICE_TRIAL
    for(U y=438;y<467;y++)for(U x=10;x<74;x++) {
    #elif defined(RECT_TRIAL)
    for(U y=438;y<462;y++)for(U x=562;x<626;x++) {
#else
    for(U y=432;y<452;y++)for(U x=562;x<640;x++) {
#endif
        U i=2*(y*640+x);if(frame_pixels[i]||frame_pixels[i+1])ink++;
    }
    printf("FRAME_CAPTURE name=%s bitmap=%08x same=%d region_nonzero=%u\n",
        name,manager[0x8c/4],!frame_bitmap||manager[0x8c/4]==frame_bitmap,ink);fflush(0);
    char path[128];snprintf(path,sizeof path,FRAME_DIR "%s.raw",name);
    f=open(path,1|64|128,0600);if(f<0)return 89; /* exclusive evidence */
    U off=0;int failed=0;
    while(off<sizeof frame_pixels){int n=write(f,frame_pixels+off,sizeof frame_pixels-off);if(n<=0){failed=1;break;}off+=(U)n;}
    if(close(f)||failed)return 89;
    if(empty){frame_bitmap=manager[0x8c/4];if(ink)return 88;}
    return 0;
}
static int frame_redraw(int pid) {
    /* Independent guardian owns this call, including parent EOF/termination. */
    U b=0;if(frame_mapping(pid,&b,0)||b!=frame_base)return 90;
    int child=fork();if(child<0)return 90;
    if(!child) {
        char pid_arg[16],base_arg[16];snprintf(pid_arg,sizeof pid_arg,"%d",pid);
        snprintf(base_arg,sizeof base_arg,"%x",frame_base);
        char *const argv[]={FRAME_REDRAW,"--request",pid_arg,base_arg,0};
        alarm(8);execv(argv[0],argv);_exit(127);
    }
    int status=0;int waited=waitpid(child,&status,0);
    printf("FRAME_REDRAW status=%d\n",status);fflush(0);
    return waited==child&&!status?0:90;
}

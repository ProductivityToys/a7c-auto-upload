/* No /proc access: exercise the read-only inspector against synthetic maps. */
#define main inspector_main
#define open fake_open
#define close fake_close
#define read fake_read
#define pread fake_pread
#define readlink fake_readlink
#define alarm fake_alarm
#include "../im_modules.c"
#undef main
extern void *memcpy(void *,const void *,unsigned);
extern void *memset(void *,int,unsigned);
static U im_image[0xe000/4], db_image[0x11000/4], heap[32];
static int scenario, maps_read, head_reads;
static const char maps_text[] =
 "00008000-00016000 r-xp 00000000 00:00 1 /usr/bin/im.elf\n"
 "00100000-00111000 rw-p 00000000 00:00 2 /usr/lib/libIMDB.so\n"
 "00200000-00200080 rw-p 00000000 00:00 0 [heap]\n";
int fake_open(const char *p,int flags,...) {
    if(flags)return -1;
    if(!strcmp(p,"/proc/123/maps"))return 10;
    if(!strcmp(p,"/proc/123/mem"))return 11;
    return -1;
}
int fake_close(int f) {return f==10||f==11?0:-1;}
unsigned fake_alarm(unsigned n) {(void)n;return 0;}
int fake_readlink(const char *p,char *out,unsigned n) {
    const char value[]="/usr/bin/im.elf";
    if(scenario==6 || strcmp(p,"/proc/123/exe") || n<sizeof value)return -1;
    memcpy(out,value,sizeof value-1);return sizeof value-1;
}
int fake_read(int f,void *out,unsigned n) {
    if(f!=10)return -1;if(maps_read++)return 0;
    if(scenario==7) {
        static char large_maps[65536];
        unsigned used=sizeof maps_text-1;
        memcpy(large_maps,maps_text,used);
        for(U i=0;i<600;i++) {
            int added=snprintf(large_maps+used,sizeof large_maps-used,
                "%08x-%08x r--p 00000000 00:00 0 [synthetic-large-map]\n",
                0x1000000+i*4096,0x1001000+i*4096);
            if(added<0 || (unsigned)added>=sizeof large_maps-used)return -1;
            used+=(unsigned)added;
        }
        if(n<used)return -1;memcpy(out,large_maps,used);return (int)used;
    }
    if(n<sizeof maps_text-1)return -1;
    memcpy(out,maps_text,sizeof maps_text-1);return sizeof maps_text-1;
}
int fake_pread(int f,void *out,unsigned n,long at) {
    if(f!=11 || at<0)return -1;
    U a=(U)at;
    if(a==0x15514 && ++head_reads==2 && scenario==5) {U changed=0;memcpy(out,&changed,4);return 4;}
    if(a>=0x8000 && a+n<=0x16000)memcpy(out,(char *)im_image+a-0x8000,n);
    else if(a>=0x100000 && a+n<=0x111000)memcpy(out,(char *)db_image+a-0x100000,n);
    else if(a>=0x200000 && a+n<=0x200080)memcpy(out,(char *)heap+a-0x200000,n);
    else return -1;
    return (int)n;
}
static void setup(int mode) {
    scenario=mode;maps_read=head_reads=0;region_count=database_base=0;memory=-1;
    memset(im_image,0,sizeof im_image);memset(db_image,0,sizeof db_image);memset(heap,0,sizeof heap);
    im_image[0]=db_image[0]=0x464c457f;
    const unsigned char signature[]={0x90,0xb5,0x85,0xb0,0x27,0x4b,0x02,0xaf};
    memcpy((char *)im_image+0x17ec,signature,8);
    im_image[(0x154ec-0x8000)/4]=1;
    im_image[(0x15514-0x8000)/4]=mode==1?0:0x200000;
    db_image[0x10600/4]=40;
    for(U i=0;i<3;i++) {
        U *entry=db_image+(0x1057c+i*44)/4;
        entry[0]=0x20000003;entry[1]=255;entry[2]=0x7fffffff;
        entry[3]=i==0?2030:i==1?2028:2031;
    }
    heap[2]=0x1105d4;heap[5]=2;
    if(mode==2)im_image[0]=0;
    if(mode==3)heap[0]=0x200000;
    if(mode==4)heap[2]=0x300000;
}
int main(void) {
    int expected[]={0,0,68,69,70,72,65,0};
    char *argv[]={"im-modules","123",0};
    for(int i=0;i<8;i++) {
        setup(i);int rc=inspector_main(2,argv);
        printf("FIXTURE scenario=%d rc=%d expected=%d\n",i,rc,expected[i]);
        if(rc!=expected[i])return 1;
    }
    printf("IM_MODULES_HOST_OK 8\n");return 0;
}

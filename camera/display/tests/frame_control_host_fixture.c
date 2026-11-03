/* Host-only controller checks. All procfs/device/output/process I/O simulated. */
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
typedef unsigned U;
#define BASE 0x06015000U
static unsigned mode,opened,map_calls,manager_reads,write_bytes,waits;
static int failure;
static unsigned char physical[614400];
static char maps_text[512];
static unsigned read_offset;
static int fake_open(const char *name,int flags,...) {
    if(strstr(name,"/maps")){read_offset=0;opened++;return 3;}
    if(!strcmp(name,"/dev/mem")){if(flags)failure=1;opened++;return 4;}
#ifdef RECT_SERVICE_TRIAL
    const char *directory="/native-service/";
#elif defined(RECT_SERIES_TRIAL)
    const char *directory="/native-rect-v17/";
#elif defined(RECT_TRIAL)
    const char *directory="/native-rect-v16/";
#elif defined(PRESENT_TRIAL)
    const char *directory="/native-present-v12/";
#else
    const char *directory="/native-frame-v9/";
#endif
    if(strstr(name,directory)&&strstr(name,".raw")) {
        if(flags!=(1|64|128))failure=1;
        if(mode==8)return -1;
        opened++;return 5;
    }
    failure=1;return -1;
}
static int fake_read(int fd,void *p,unsigned size) {
    if(fd!=3){failure=1;return -1;}
    unsigned left=(unsigned)strlen(maps_text)-read_offset,n=left<size?left:size;
    memcpy(p,maps_text+read_offset,n);read_offset+=n;return (int)n;
}
static int fake_close(int fd){if(fd<3||fd>5||!opened)failure=1;else opened--;return 0;}
static int fake_write(int fd,const void *p,unsigned size){
    if(fd!=5||!p)failure=1;if(mode==5)return -1;write_bytes+=size;return (int)size;
}
static int rd(U address,void *p,U size) {
    memset(p,0,size);U *w=p;
    if(address==BASE+0x1453df0&&size==256){w[0x58/4]=1;w[0x8c/4]=0x10000000+(mode==6&&manager_reads?4:0);manager_reads++;}
    else if(address==0x10000000&&size==128){w[0]=BASE+0x13b1f50;w[1]=0x10001000;w[2]=0x20000000;}
    else if(address==0x10001000&&size==64){w[4]=(480U<<16)|640;w[6]=w[4];w[7]=1;w[9]=mode>=9?0x22ab2000:mode==1?0xfe34a000:0xfe33a000;}
    else if(address==BASE+0x145aac8&&size==28){w[0]=BASE+0x13b5238;w[2]=BASE+0x13b5288;w[3]=1;w[5]=1;}
    else if(address==BASE+0x145aae4&&size==208){if(mode==2)((unsigned char *)p)[18]=1;}
    else {failure=1;return -1;}
    return 0;
}
#define open fake_open
#define read fake_read
#define close fake_close
#define write fake_write
#define mmap64 fake_mmap64
#define munmap fake_munmap
#define execv fake_execv
#define fork fake_fork
#define waitpid fake_waitpid
#define alarm fake_alarm
#define _exit fake_exit
static int fake_fork(void){return 123;}
static int fake_waitpid(int pid,int *status,int flags){if(pid!=123||flags)failure=1;*status=0;waits++;return pid;}
static unsigned fake_alarm(unsigned n){return n;}
static void fake_exit(int status){(void)status;failure=1;}
#include "../module/frame_control.h"
void *fake_mmap64(void *p,unsigned n,int prot,int flags,int fd,long long off){
    if(p||n!=sizeof physical||prot!=1||flags!=1||fd!=4||off!=(mode>=9?0x22ab2000LL:0xfe33a000LL))failure=1;
    map_calls++;return physical;
}
int fake_munmap(void *p,unsigned n){if(p!=physical||n!=sizeof physical)failure=1;return mode==4?-1:0;}
int fake_execv(const char *p,char *const *argv){(void)p;(void)argv;failure=1;return -1;}
int main(void) {
    const int expected[]={0,87,88,88,89,89,89,87,89,
#ifdef RECT_SERVICE_TRIAL
        0,87,87,87
#else
        87,87,87,87
#endif
    };
    for(mode=0;mode<sizeof expected/sizeof expected[0];mode++) {
        failure=0;opened=map_calls=manager_reads=write_bytes=waits=0;
        memset(physical,0,sizeof physical);
#ifdef RECT_SERVICE_TRIAL
        if(mode==3)physical[2*(466*640+73)]=1;
#elif defined(RECT_TRIAL)
        if(mode==3)physical[2*(461*640+625)]=1; /* includes lower-right border */
#else
        if(mode==3)physical[2*(432*640+562)]=1;
#endif
        snprintf(maps_text,sizeof maps_text,
            "06015000-09015000 r-xp 00000000 00:01 1 /usr/lib/libObj.so\n"
            "20000000-%08x rw-s fe33a000 00:01 2 /dev/mem\n",mode==7?0x20095000:0x20096000);
        if(mode>=9)snprintf(maps_text,sizeof maps_text,
            "06015000-09015000 r-xp 00000000 00:01 1 /usr/lib/libObj.so\n"
            "20000000-%08x rw-s %08x 00:01 2 %s\n",
            mode==12?0x20095000:0x20096000,mode==10?0x22ab3000:0x22ab2000,
            mode==11?"/dev/mem":"/dev/stream");
        frame_base=BASE;frame_bitmap=0;
        int rc=frame_snapshot(162,"before",1);
        if(rc!=expected[mode]||opened)failure=1;
        if((mode==1||mode==2||mode==7)&&map_calls)failure=1;
        printf("FRAME_CONTROL mode=%u rc=%d maps=%u bytes=%u failed=%d\n",mode,rc,map_calls,write_bytes,failure);
        if(failure)return 1;
    }
    mode=0;failure=0;
    if(frame_redraw(162)||waits!=1||opened||failure)return 2;
    frame_base++;
    if(frame_redraw(162)!=90||waits!=1||opened||failure)return 3;
    printf("FRAME_CONTROL_OK 15\n");return 0;
}

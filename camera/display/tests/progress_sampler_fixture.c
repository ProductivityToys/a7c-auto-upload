#ifdef NATIVE_RECT_SAMPLE
#define SAMPLE_DELAY 1000
#define SAMPLE_TOTAL 4000
#define SLOT_ENABLED 0
#else
#define SAMPLE_DELAY 10000
#define SAMPLE_TOTAL 10000
#define SLOT_ENABLED 1
#endif
#define open sample_open
#define close sample_close
#define pread sample_pread
#define readlink sample_readlink
#define mmap sample_mmap
#define munmap sample_munmap
#define clock_gettime sample_clock
#define usleep sample_sleep
#define main sample_main
#include "../progress_sampler.c"
#undef main
#include <assert.h>
static u32 tick;static int mode,maps,closes,contexts;
static unsigned char screen[614400];
int sample_open(const char *p,int flags,...){assert(flags==O_RDONLY);return !strcmp(p,"/dev/mem")?20:10;}
int sample_close(int fd){assert(fd==10||fd==20);closes++;return 0;}
ssize_t sample_readlink(const char *p,char *out,size_t n){(void)p;const char *s="/usr/bin/im.elf";assert(n>strlen(s));memcpy(out,s,strlen(s));return strlen(s);}
ssize_t sample_pread(int fd,void *out,size_t n,off_t off){
 assert(fd==10);memset(out,0,n);u32 *v=out;
 if(off==0x6015000&&n==4)v[0]=0x464c457f;
 else if(off==0x6015000+0x1453df0U&&n==256){v[0x58/4]=1;v[0x8c/4]=(mode==2&&contexts++>1)?0x4000:0x2000;}
 else if((off==0x2000||off==0x4000)&&n==128){v[0]=0x6015000+0x13b1f50U;v[1]=0x3000;}
 else if(off==0x3000&&n==64){v[4]=640|(480<<16);v[6]=v[4];v[7]=1;v[9]=mode==1?0:0xfe33a000U;}
 else if(off==0x6015000+0x145aae4U&&n==208){unsigned char *s=out;s[18]=1;s[204]=SLOT_ENABLED;s[200]=562&255;s[201]=562>>8;s[202]=432&255;s[203]=432>>8;s[22]=0x16;s[23]=0x6b;}
 else if(off==0x6015000+0x14539b4U&&n==1)*(unsigned char *)out=2;
 else assert(0);
 return n;
}
void *sample_mmap(void *a,size_t n,int prot,int flags,int fd,off_t off){assert(!a&&n==sizeof screen&&prot==PROT_READ&&flags==MAP_SHARED&&fd==20&&off==0xfe33a000LL);maps++;return screen;}
int sample_munmap(void *p,size_t n){assert(p==screen&&n==sizeof screen);maps--;return 0;}
int sample_clock(clockid_t id,struct timespec *t){assert(id==CLOCK_MONOTONIC);t->tv_sec=tick/1000;t->tv_nsec=tick%1000*1000000;return 0;}
int sample_sleep(useconds_t u){assert(u==SAMPLE_DELAY);tick+=u/1000;
 if(mode==0){unsigned short *v=(void *)screen;const unsigned points[6]={438*640+562,438*640+594,438*640+625,461*640+562,461*640+594,461*640+625};for(unsigned i=0;i<6;i++)v[points[i]]=0;}
#ifdef NATIVE_RECT_SAMPLE
 if(mode==3){
  unsigned short *v=(void *)screen;memset(screen,0,sizeof screen);
  unsigned width=tick>=1&&tick<=3?10:tick==5?22:tick>=8&&tick<=9?46:0;
  if(width){
   const unsigned points[6]={438*640+562,438*640+594,438*640+625,461*640+562,461*640+594,461*640+625};
   for(unsigned i=0;i<6;i++)v[points[i]]=65535;
   for(unsigned x=564;x<564+width;x++)v[450*640+x]=65535;
  }
 }
#endif
 return 0;}
int main(void){
 char *args[]={"sample","162","6015000",0};
 memset(screen,255,sizeof screen);assert(sample_main(3,args)==0);assert(tick==SAMPLE_TOTAL&&maps==0&&closes==2);
 mode=1;tick=0;closes=0;contexts=0;assert(sample_main(3,args)==67);assert(maps==0&&closes==1&&tick==0);
 mode=2;tick=0;closes=0;contexts=0;assert(sample_main(3,args)==71);assert(maps==0&&closes==2&&tick==50*SAMPLE_DELAY/1000);
#ifdef NATIVE_RECT_SAMPLE
 mode=3;tick=0;closes=0;contexts=0;memset(screen,0,sizeof screen);
 assert(sample_main(3,args)==0);assert(maps==0&&closes==2);
#endif
 return 0;
}

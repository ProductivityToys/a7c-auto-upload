/* Explicit bounded (20 seconds / 1000 samples), read-only ILCE-7C2.00 DDS/OSD sampling diagnostic.
 * No writes, messages, threads, leases or persistent files. Output is stdout.
 * V2 records: dt, border/slot flags, level, zero mask, min/max16LE,
 * six native control pixels, native redraw countdown. Sequential, not atomic.
 * Samples are sequential observations, not an atomic LCD scanout capture. */
#include "../uploader/compat.h"
#ifdef __arm__
extern int printf(const char *,...),fflush(void *),pread(int,void *,unsigned,long);
extern int readlink(const char *,char *,unsigned);
extern void *mmap64(void *,unsigned,int,int,int,long long);
extern int munmap(void *,unsigned);
#else
#include <sys/mman.h>
#define mmap64 mmap
#endif
static unsigned short half(const unsigned char *p){return p[0]|((unsigned)p[1]<<8);}
static int at(int fd,u32 address,void *p,unsigned n){return pread(fd,p,n,(long)address)!=(int)n;}
static int context(int fd,u32 base,u32 *bitmap){
 u32 manager[64],obj[32],desc[16];
 if(at(fd,base+0x1453df0U,manager,sizeof manager)||manager[0x58/4]!=1||!manager[0x8c/4])return 1;
 u32 b=manager[0x8c/4];
 if(at(fd,b,obj,sizeof obj)||obj[0]!=base+0x13b1f50U||!obj[1]||at(fd,obj[1],desc,sizeof desc))return 1;
 if(desc[9]!=0xfe33a000U||desc[7]!=1||half((void*)desc+16)!=640||half((void*)desc+18)!=480||
    half((void*)desc+24)!=640||half((void*)desc+26)!=480||(*bitmap&&*bitmap!=b))return 1;
 *bitmap=b;return 0;
}
#ifndef NATIVE_RECT_SAMPLE
static unsigned level(const unsigned char *s){
 unsigned total=0,partial=0;
 for(unsigned i=0;i<4;i++){
  unsigned v=(s[22+i/2]>>(i%2?0:4))&15,lo=i==0?1:i==3?11:6;
  if(v<lo||v>lo+4||(partial&&v!=lo))return 255;
  total+=v-lo;if(v<lo+4)partial=1;
 }
 for(unsigned i=24;i<30;i++)if(s[i])return 255;
 return total<=15?total:255;
}
#endif
int main(int argc,char **argv){
 if(argc!=3)return 64;
 int pid=atoi(argv[1]);char *end=0;u64 address=strtoull(argv[2],&end,16);
 if(pid<2||!end||*end||address>0x70000000U)return 64;
 u32 base=(u32)address,magic=0,bitmap=0;char path[80],target[80];
 snprintf(path,sizeof path,"/proc/%d/exe",pid);int n=readlink(path,target,sizeof target-1);
 if(n<0||n>=(int)sizeof target-1)return 65;target[n]=0;
 if(strcmp(target,"/usr/bin/im.elf"))return 65;
 snprintf(path,sizeof path,"/proc/%d/mem",pid);int fd=open(path,O_RDONLY);if(fd<0)return 66;
 if(at(fd,base,&magic,4)||magic!=0x464c457f||context(fd,base,&bitmap)){close(fd);return 67;}
 int dev=open("/dev/mem",O_RDONLY);if(dev<0){close(fd);return 68;}
 void *map=mmap64(0,614400,1,1,dev,0xfe33a000LL);
 if(map==(void*)-1){close(dev);close(fd);return 68;}
 const volatile unsigned short *pixels=map;
 const unsigned points[6]={438*640+562,438*640+594,438*640+625,461*640+562,461*640+594,461*640+625};
 const unsigned controls[6]={43*640+44,14*640+322,98*640+451,96*640+510,451*640+437,203*640+581};
#ifdef NATIVE_RECT_SAMPLE
 const unsigned limit=4000,delay=1000;
 unsigned hist[64]={0},first_full=0,last_full=0,nonzero=0;
 unsigned widths[61]={0},pending_gap=0,gaps=0,gap_samples=0,max_gap=0;
#else
 const unsigned limit=1000,delay=10000;
#endif
 unsigned char records[4000][10];unsigned used=0,rc=0;u32 began=millis(),last=began;
 for(;used<limit;used++){
  unsigned char s[208];u32 now=millis();
  if(now-began>=20000)break;
  if((used%50==0&&context(fd,base,&bitmap))||at(fd,base+0x145aae4U,s,sizeof s)){rc=69;break;}
#ifndef NATIVE_RECT_SAMPLE
  if(half(s+200)!=562||half(s+202)!=432||s[18]!=1){rc=70;break;}
#else
  /* Native rectangle trial does not enable or mutate a DDS text slot. */
  if(s[204]){rc=70;break;}
#endif
  unsigned mask=0,zero=0,lo=65535,hi=0,native=0;
  for(unsigned j=0;j<6;j++){
   unsigned v=pixels[points[j]];
   if(v==0xffff)mask|=1U<<j;if(!v)zero|=1U<<j;
   if(v<lo)lo=v;if(v>hi)hi=v;
   if(pixels[controls[j]]>=0x8880)native|=1U<<j;
  }
  unsigned char redraw=0;
  if(at(fd,base+0x14539b4U,&redraw,1)){rc=69;break;}
  unsigned delta=now-last;
  records[used][0]=(unsigned char)(delta>255?255:delta);
  records[used][1]=(unsigned char)(mask|((s[204]?1:0)<<6)|128);
#ifdef NATIVE_RECT_SAMPLE
  unsigned fill=0;for(unsigned x=564;x<624;x++)if(pixels[450*640+x]==0xffff)fill++;
  records[used][2]=fill;
  if(mask==63){
   widths[fill]++;
   if(pending_gap){gaps++;gap_samples+=pending_gap;if(pending_gap>max_gap)max_gap=pending_gap;pending_gap=0;}
  }else if(hist[63])pending_gap++;
  hist[mask]++;if(hi)nonzero++;
  if(mask==63){if(hist[63]==1)first_full=now;last_full=now;}
#else
  records[used][2]=(unsigned char)level(s);
#endif
  records[used][3]=zero;records[used][4]=lo;records[used][5]=lo>>8;
  records[used][6]=hi;records[used][7]=hi>>8;
  records[used][8]=native;records[used][9]=redraw;last=now;
  usleep(delay);
 }
 int unmap=munmap(map,614400),dc=close(dev),fc=close(fd);
 printf("SAMPLER version=2 began_ms=%u end_ms=%u samples=%u rc=%u unmap=%d close=%d,%d\n",began,millis(),used,rc,unmap,dc,fc);
#ifdef NATIVE_RECT_SAMPLE
 printf("NATIVE_RECT_SAMPLES full=%u nonzero=%u first_full_ms=%u last_full_ms=%u nominal_delay_us=%u\n",hist[63],nonzero,first_full,last_full,delay);
 for(unsigned i=0;i<64;i++)if(hist[i])printf("MASK value=%u count=%u\n",i,hist[i]);
 printf("NATIVE_RECT_GAPS count=%u samples=%u max_samples=%u excludes_before_after=1\n",gaps,gap_samples,max_gap);
 for(unsigned i=0;i<61;i++)if(widths[i])printf("FILL width=%u count=%u\n",i,widths[i]);
 (void)records;
#else
 for(unsigned i=0;i<used;i++){
  if(i%100==0)printf("R index=%u data=",i);
  for(unsigned j=0;j<10;j++)printf("%02x",records[i][j]);
  if(i%100==99||i+1==used)printf("\n");
 }
#endif
 fflush(0);return rc||unmap||dc||fc?71:0;
}

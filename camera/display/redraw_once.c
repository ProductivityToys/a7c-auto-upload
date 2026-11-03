/* Exact ILCE-7C 2.00 research. Host must verify firmware/library hashes first.
 * Request native full redraw by setting its existing RAM countdown to 2,
 * matching native initialization. No pixel, object, function or disk writes.
 * This is NOT a public ABI or a production overlay backend. Pending redraw
 * is left to the native renderer; never roll pixels or counters back blindly.
 */
#include "../uploader/compat.h"
#ifdef __arm__
extern int pread(int,void *,unsigned,long),pwrite(int,const void *,unsigned,long);
extern int printf(const char *,...),fflush(void *),readlink(const char *,char *,unsigned);
extern void *memcpy(void *,const void *,unsigned);
extern int memcmp(const void *,const void *,unsigned);
#endif
#define COUNTER 0x14539b4U
#define CALLBACKS 0x14539d8U
static int fd=-1;
static u32 base;
static int rd(u32 a,void *p,unsigned n){return a<0x80000000U && n && a+n>a && pread(fd,p,n,(long)a)==(int)n?0:-1;}
static int valid(void){
 u32 magic,table,callbacks[6];
 unsigned char reader[16],decrement[16];
 static const unsigned char want_reader[16]={0x04,0x4b,0x80,0xb5,0x7b,0x44,0x00,0xaf,0x18,0x78,0x00,0x38,0x18,0xbf,0x01,0x20};
 static const unsigned char want_decrement[16]={0x04,0x4b,0x80,0xb5,0x7b,0x44,0x00,0xaf,0x1a,0x78,0x0a,0xb1,0x01,0x3a,0x1a,0x70};
 if(rd(base,&magic,4)||magic!=0x464c457f||rd(base+0x1453914U,&table,4)||table!=base+CALLBACKS||
    rd(table,callbacks,sizeof callbacks)||callbacks[3]!=base+0x674db9U||
    callbacks[4]!=base+0x674a95U||callbacks[5]!=base+0x674aadU||
    rd(base+0x674a94U,reader,sizeof reader)||memcmp(reader,want_reader,sizeof reader)||
    rd(base+0x674aacU,decrement,sizeof decrement)||memcmp(decrement,want_decrement,sizeof decrement))return 65;
 return 0;
}
static int request(void){
 unsigned char n=255;
 if(valid()||rd(base+COUNTER,&n,1)||n!=0)return 66;
 n=2;
 if(pwrite(fd,&n,1,(long)(base+COUNTER))!=1)return 67;
 printf("REDRAW_REQUEST value=2 bytes=1\n");fflush(0);return 0;
}
int main(int argc,char **argv){
 u32 started=millis();
 if(argc!=4 || (strcmp(argv[1],"--inspect")&&strcmp(argv[1],"--request")))return 64;
 char *end=0;unsigned long long a=strtoull(argv[3],&end,16);
 int pid=atoi(argv[2]);
 if(!end||*end||a<0x1000000ULL||a>0x30000000ULL||(a&4095)||pid<2)return 64;
 base=(u32)a;char path[64],exe[96];snprintf(path,sizeof path,"/proc/%d/exe",pid);
 int len=readlink(path,exe,sizeof exe-1);if(len<0)return 64;exe[len]=0;
 if(strcmp(exe,"/usr/bin/im.elf"))return 64;
 snprintf(path,sizeof path,"/proc/%d/mem",pid);
 fd=open(path,!strcmp(argv[1],"--inspect")?O_RDONLY:2 /* O_RDWR */);
 unsigned char n=255;
 if(fd<0||valid()||rd(base+COUNTER,&n,1))return 65;
 printf("REDRAW_STATE before=%u\n",n);fflush(0);
 if(!strcmp(argv[1],"--inspect")){close(fd);return 0;}
 int r=request();if(r){close(fd);return r;}
 /* One already-validated, read-only layout query wakes the UI event loop.
  * Killing this client does not retract that harmless queued query. */
 int child=fork();if(child<0){close(fd);return 68;}
 if(!child){
  char *const args[]={"/usr/bin/testcmd.elf","--sync","0x0083014b","5","1","1","1",0};
  close(fd);execv(args[0],args);_exit(127);
 }
 int child_done=0,status=0,consumed=0;unsigned last=255;
 while(millis()-started<6000){
  if(!child_done){int w=waitpid(child,&status,1 /* WNOHANG */);if(w==child)child_done=1;else if(w<0)break;}
  if(valid()||rd(base+COUNTER,&n,1))break;
  if(last!=n){printf("REDRAW_STATE counter=%u elapsed=%u\n",n,millis()-started);fflush(0);last=n;}
  if(n>2)break; /* Native concurrent invalidation: preserve it, stop our trial. */
  if(!n)consumed=1;
  if(consumed&&child_done)break;
  usleep(20000);
 }
 if(!child_done){kill(child,15);usleep(100000);if(waitpid(child,&status,1)==0){kill(child,9);waitpid(child,&status,0);}}
 close(fd);
 printf("REDRAW_DONE consumed=%d query_status=%d elapsed=%u\n",consumed,status,millis()-started);fflush(0);
 return consumed&&child_done&&status==0?0:69;
}

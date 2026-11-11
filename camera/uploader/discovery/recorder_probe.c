/* ILCE-7C 2.00 recorder hints and optional native FTP switch read.
 * Read-only procfs, no native calls, hooks, ptrace, or media access.
 */
#include "../compat.h"
#ifdef __arm__
extern int pread64(int,void*,unsigned,long long);
#else
#define pread64 pread
#endif
#ifndef A7C_CANCEL_PATH
#define A7C_CANCEL_PATH "/setting/a7c-debug/ram/dds-once/recorder-watch.stop"
#endif
#ifndef A7C_UPLOADER_STOP
#define A7C_UPLOADER_STOP "/setting/a7c-uploader/ram/stop"
#endif
#ifndef A7C_PROC_ROOT
#define A7C_PROC_ROOT "/proc"
#endif
#ifndef A7C_LINK_INDEX
#define A7C_LINK_INDEX "/sys/class/net/wlan0/ifindex"
#endif
static char maps[131072],path[160];
static unsigned char sample[1052];
/* Original DebugDispRecInfo entry, verified from b4c0f0e8...libmpr.so. */
static const unsigned char entry[16]={0x07,0x4b,0x80,0xb5,0x00,0xaf,0x1b,0x68,0x1b,0xb9,0x06,0x48,0xf0,0xf7,0x5c,0xff};
static int equal(const void *a,const void *b,unsigned n){const unsigned char*x=a,*y=b;for(unsigned i=0;i<n;i++)if(x[i]!=y[i])return 0;return 1;}
static u32 le(const unsigned char*p){return (u32)p[0]|(u32)p[1]<<8|(u32)p[2]<<16|(u32)p[3]<<24;}
static int hex(const char **p,u32 *v){unsigned n=0;*v=0;while(**p){unsigned c=(unsigned char)**p,d;if(c>='0'&&c<='9')d=c-'0';else if(c>='a'&&c<='f')d=c-'a'+10;else break;if(++n>8)return 0;*v=(*v<<4)|d;(*p)++;}return n!=0;}
static int ends(const char*p,const char*s){unsigned n=strlen(p),m=strlen(s);return n>=m&&equal(p+n-m,s,m);}
static int readable(u32 at,unsigned n){
 if(!n||at>0xffffffffU-n)return 0;
 for(char*p=maps;*p;){const char*q=p;u32 lo,hi;if(hex(&q,&lo)&&*q++=='-'&&hex(&q,&hi)&&*q++==' '&&*q=='r'&&lo<=at&&at+n<=hi)return 1;while(*p&&*p!='\n')p++;if(*p)p++;}return 0;
}
static int getfile(const char*name,void*out,unsigned cap){int f=open(name,O_RDONLY);if(f<0)return -1;unsigned used=0;int n;while(used<cap){n=read(f,(char*)out+used,cap-used);if(n<0){close(f);return -1;}if(!n)break;used+=(unsigned)n;}close(f);return (int)used;}
static u32 library_base(const char *name)
{
 u32 base=0; unsigned matches=0;
 for(char *line=maps; *line;){
  char *end=line; while(*end&&*end!='\n')end++;
  char saved=*end; *end=0;
  const char *field=line; u32 lo,hi,offset;
  if(hex(&field,&lo)&&*field++=='-'&&hex(&field,&hi)&&*field++==' '&&
     hi>lo&&end-field>=5&&equal(field,"r-xp ",5)){
   field+=5;
   if(hex(&field,&offset)&&offset==0&&ends(field,name)){base=lo;matches++;}
  }
  *end=saved; line=saved?end+1:end;
 }
 return matches==1?base:0;
}
static int read_at(int mem,u32 address,void *out,unsigned size)
{
 return readable(address,size)&&pread64(mem,out,size,(u64)address)==(int)size;
}
static int ftp_master(int mem,u32 base)
{
 /* The stock 2.00 menu setter writes item 4 of its FTP settings cache.
  * Only follow that row's exact relocated pointer. Zero is uninitialized.
  */
 const u32 cache=0xd3cf98,slot=0xcce200;
 const unsigned char setter[16]={0x40,0xf2,0x01,0x11,0x80,0xf6,0xb4,0xe7,0x04,0x20,0x21,0x46,0x7b,0xf6,0xc2,0xe4};
 const unsigned char update[16]={0x10,0x4b,0xe3,0x58,0x1b,0x68,0x9d,0x42,0x10,0xda,0x0f,0x4b,0x18,0x22,0xe3,0x58};
 unsigned char code[16], pointer[4], value[4], again[4];
 if(!base||base>0xffffffffU-cache-4||
    !read_at(mem,base+0x704f3a,code,sizeof code)||!equal(code,setter,sizeof code)||
    !read_at(mem,base+0x56bf60,code,sizeof code)||!equal(code,update,sizeof code)||
    !read_at(mem,base+slot,pointer,4)||le(pointer)!=base+cache||
    !read_at(mem,base+cache,value,4)||
    !read_at(mem,base+slot,again,4)||!equal(pointer,again,4)||
    !read_at(mem,base+cache,again,4)||!equal(value,again,4))return 95;
 switch(le(value)){
  case 1: return write(1,"off\n",4)==4?0:74;
  case 2: return write(1,"on\n",3)==3?0:74;
  default: return 95;
 }
}
/* Sony standby freezes the system clocks. Network device generation survives
 * that ambiguity; the worker supplies its previous value across wait calls. */
static unsigned link_index(void){
 char text[16];int n=getfile(A7C_LINK_INDEX,text,sizeof text);unsigned value=0;
 if(n<2||n>11||text[n-1]!='\n')return 0;
 for(int i=0;i<n-1;i++){
  if(text[i]<'0'||text[i]>'9'||value>214748364U)return 0;
  value=value*10+(unsigned)(text[i]-'0');if(value>2147483647U)return 0;
 }
 return value;
}
int main(int argc,char **argv){
 unsigned seconds=0,link_seen=0,link_current=0;int waiting=0;
 int ftp_query=argc==3&&!strcmp(argv[2],"ftp-master");
 if(argc!=2&&!ftp_query){
  if(argc!=4&&argc!=5)return 64;
  if(!strcmp(argv[2],"wait"))waiting=1;else if(strcmp(argv[2],"watch"))return 64;
  if(argc!=(waiting?5:4))return 64;
  if(waiting){
   unsigned digits=0;
   for(const char*p=argv[4];*p;p++){
    if(*p<'0'||*p>'9'||++digits>10||link_seen>214748364U)return 64;
    link_seen=link_seen*10+(unsigned)(*p-'0');if(link_seen>2147483647U)return 64;
   }
   if(!digits)return 64;
  }
  unsigned n=0;for(const char*p=argv[3];*p;p++){if(*p<'0'||*p>'9'||++n>4)return 64;seconds=seconds*10+(unsigned)(*p-'0');}
  if(!seconds||seconds>(waiting?30U:1800U))return 64;
 }
 unsigned pid=0,digits=0;
 for(const char*p=argv[1];*p;p++){if(*p<'0'||*p>'9'||++digits>9)return 64;pid=pid*10+(unsigned)(*p-'0');}
 if(pid<=1||pid>2147483647U)return 64;
 snprintf(path,sizeof path,A7C_PROC_ROOT "/%u/comm",pid);char comm[16];int n=getfile(path,comm,sizeof comm-1);if(n<0)return 72;comm[n]=0;if(strcmp(comm,"im.elf\n"))return 95;
 snprintf(path,sizeof path,A7C_PROC_ROOT "/%u/maps",pid);n=getfile(path,maps,sizeof maps-1);if(n<=0||n==(int)sizeof maps-1)return 95;maps[n]=0;
 u32 base=library_base(ftp_query?" /usr/lib/viewUnified2.so":" /usr/lib/libmpr.so");
 if(!base||(!ftp_query&&(base>0xffffffffU-0x153643cU||!readable(base+0x1536438,4))))return 95;
 snprintf(path,sizeof path,A7C_PROC_ROOT "/%u/mem",pid);int mem=open(path,O_RDONLY);if(mem<0)return 72;
 if(ftp_query){int rc=ftp_master(mem,base);close(mem);return rc;}
 unsigned char code[16],ptr[4],before[4],signature[112],previous[112];int rc=95,have=0,activity=0;int owner=getppid();unsigned emissions=0,samples=0;u32 started=millis();struct timespec cpu_start,cpu_end;int cpu_ok=!clock_gettime(2,&cpu_start);
 if(pread64(mem,code,16,(u64)base+0x8a9fe4)!=16||!equal(code,entry,16))goto done;
 for(;;){
  samples++;
  if(pread64(mem,ptr,4,(u64)base+0x1536438)!=4)goto done;
  u32 core=le(ptr);if(!core||core>0xffffffffU-0x1ac8U||!readable(core+0x16ac,sizeof sample))goto done;
  if(pread64(mem,sample,sizeof sample,(u64)core+0x16ac)!=(int)sizeof sample)goto done;
  if(pread64(mem,before,4,(u64)base+0x1536438)!=4||!equal(ptr,before,4))goto done;
  for(unsigned i=0;i<4;i++){
   unsigned char*p=sample+i*0x108,*q=signature+i*28;
   /* Ignore unrelated recorder fields and inactive line contents. */
   for(unsigned j=0;j<28;j++)q[j]=0;
   q[4]=p[4];
   if(p[4])for(unsigned j=0;j<4;j++){q[j]=p[j];q[8+j]=p[8+j];q[12+j]=p[0xf0+j];q[16+j]=p[0xfc+j];q[20+j]=p[0x100+j];}
  }
  if(waiting){
   link_current=link_index();if(link_current!=link_seen){rc=12;goto done;}
   int busy=0;
   for(unsigned i=0;i<4;i++){
    unsigned char*p=signature+i*28;if(!p[4])continue;
    /* Unknown layouts fail back to ordinary polling, never an idle proof. */
    if(p[4]!=1||le(p)!=i||(le(p+8)!=256&&le(p+8)!=1)||le(p+12)>12)goto done;
    if(le(p+12)!=1||le(p+16)||le(p+20))busy=1;
   }
   if(busy||(have&&!equal(signature,previous,sizeof signature)))activity=1;
   if(!access(A7C_UPLOADER_STOP,0)){rc=20;goto done;}
   if(getppid()!=owner){rc=72;goto done;}
   if(activity&&!busy){rc=10;goto done;}
   if(millis()-started>=seconds*1000U){rc=busy?11:0;goto done;}
   for(unsigned i=0;i<sizeof signature;i++)previous[i]=signature[i];have=1;
   usleep(1000000);continue;
  }
  if(!have||!equal(signature,previous,sizeof signature)){
   if(emissions++>=256){rc=71;goto done;}
   char out[256];n=snprintf(out,sizeof out,"A7C_RECORDER_SAMPLE_V1 pid=%u ms=%u\n",pid,millis());write(1,out,(unsigned)n);
   for(unsigned i=0;i<4;i++){unsigned char*p=signature+i*28;
    n=snprintf(out,sizeof out,"line=%u active=%u index=%u type=%u state=%u count1=%u count2=%u\n",i,p[4],le(p),le(p+8),le(p+12),le(p+16),le(p+20));write(1,out,(unsigned)n);
   }
   for(unsigned i=0;i<sizeof signature;i++)previous[i]=signature[i];have=1;
  }
  if(!seconds||millis()-started>=seconds*1000U||!access(A7C_CANCEL_PATH,0)){rc=0;break;}
  usleep(1000000);
 }
 done:
 if(seconds){
  int cpu_ms=-1;if(cpu_ok&&!clock_gettime(2,&cpu_end))cpu_ms=(int)((cpu_end.tv_sec-cpu_start.tv_sec)*1000+(cpu_end.tv_nsec-cpu_start.tv_nsec)/1000000);
  char end[180];int size=snprintf(end,sizeof end,"A7C_RECORDER_%s_DONE rc=%d elapsed_ms=%u cpu_ms=%d samples=%u link_index=%u\n",waiting?"WAIT":"WATCH",rc,millis()-started,cpu_ms,samples,link_current);write(1,end,(unsigned)size);
 }
 close(mem);return rc;
}

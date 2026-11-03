/* Ordinary FTP transport, bounded streaming and length-confirmed publication.
 * Password is one line on stdin, never argv/config/log. No receiver RPCs.
 * Exit 75 retryable; 90 conflict/unsupported; 64 invalid invocation.
 */
#include "../compat.h"
#include "../sha256.h"
#include "../receipt/receipt.h"
#ifdef __arm__
extern int socket(int,int,int),connect(int,const void*,unsigned),getsockopt(int,int,int,void*,unsigned*),fcntl(int,int,...),sscanf(const char*,const char*,...);
extern unsigned short htons(unsigned short); extern unsigned inet_addr(const char*);
extern char *strstr(const char*,const char*),*strchr(const char*,int);
extern int memcmp(const void*,const void*,unsigned); extern void *memcpy(void*,const void*,unsigned),*memset(void*,int,unsigned);
struct addr4 {unsigned short family,port;unsigned addr;char zero[8];};
#define AF_INET 2
#define SOCK_STREAM 1
#define SOL_SOCKET 1
#define SO_ERROR 4
#define EINPROGRESS 115
#define F_GETFL 3
#define F_SETFL 4
#else
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#define addr4 sockaddr_in
#endif
static u32 began,limit;
static volatile int cancelled;
static int owner;
static char response[8192];
static unsigned char block[65536];
#define A7C_PROGRESS_WRITER 1
#include "../upload_progress.h"
static void stop(int sig){cancelled=sig;}
static int expired(void){return cancelled || (owner && getppid()!=owner) || millis()-began>=limit;}
static int ready(int fd,short events,u32 since){
 while(!expired()&&millis()-since<30000){struct pollfd p={fd,events,0};int n=poll(&p,1,100);if(n>0)return 1;if(n<0&&errno!=EINTR)return 0;}return 0;
}
static int send_all(int fd,const void *buf,unsigned n){
 const unsigned char*p=buf;unsigned off=0;u32 t=millis();
 while(off<n){if(!ready(fd,4,t))return 0;int r=write(fd,p+off,n-off);if(r>0){off+=(unsigned)r;t=millis();}else if(r<0&&(errno==EINTR||errno==EAGAIN))continue;else return 0;}return 1;
}
static int connect_ip(const char*ip,unsigned port){
 int fd=socket(AF_INET,SOCK_STREAM,0);if(fd<0)return -1;
 if(fcntl(fd,F_SETFL,O_NONBLOCK)<0){close(fd);return -1;}
 struct addr4 a;memset(&a,0,sizeof(a));
#ifdef __arm__
 a.family=AF_INET;a.port=htons(port);a.addr=inet_addr(ip);
#else
 a.sin_family=AF_INET;a.sin_port=htons(port);a.sin_addr.s_addr=inet_addr(ip);
#endif
 if(connect(fd,(const void*)&a,sizeof(a))<0&&errno!=EINPROGRESS){close(fd);return -1;}
 if(!ready(fd,4,millis())){close(fd);return -1;}
 int err=0;unsigned len=sizeof(err);if(getsockopt(fd,SOL_SOCKET,SO_ERROR,&err,&len)||err){close(fd);return -1;}return fd;
}
static int reply(int fd){
 char line[1024];unsigned n=0,total=0;int first=0,multi=0;u32 t=millis();response[0]=0;
 while(!expired()){
  if(!ready(fd,1,t))return -1;char c;int got=read(fd,&c,1);
  if(got<0&&(errno==EAGAIN||errno==EINTR))continue;
  if(got!=1||!c||total>=sizeof(response)-1||n>=sizeof(line)-1)return -1;
  response[total++]=c;response[total]=0;line[n++]=c;
  if(c!='\n')continue;line[n]=0;
  if(n<5||line[n-2]!='\r')return -1;
  int code=0;
  if(line[0]>='1'&&line[0]<='5'&&line[1]>='0'&&line[1]<='9'&&line[2]>='0'&&line[2]<='9')code=(line[0]-'0')*100+(line[1]-'0')*10+line[2]-'0';
  if(!first){if(!code||(line[3]!=' '&&line[3]!='-'))return -1;first=code;multi=line[3]=='-';if(!multi)return code;}
  else if(code==first&&line[3]==' ')return code;
  n=0;
 }return -1;
}
static int command(int fd,const char*verb,const char*arg){char cmd[1024];int n=snprintf(cmd,sizeof(cmd),"%s%s%s\r\n",verb,*arg?" ":"",arg);if(n<0||n>=(int)sizeof(cmd)||!send_all(fd,cmd,n))return -1;return reply(fd);}
static int decimal(const char*s,u64*out){*out=0;if(!*s)return 0;for(;*s;s++){if(*s<'0'||*s>'9'||*out>1844674407370955161ULL||(*out==1844674407370955161ULL&&*s>'5'))return 0;*out=*out*10+(*s-'0');}return 1;}
static int hex(const char*s,unsigned char*out){if(strlen(s)!=64)return 0;for(unsigned i=0;i<64;i++){unsigned c=s[i],v;if(c>='0'&&c<='9')v=c-'0';else if(c>='a'&&c<='f')v=c-'a'+10;else return 0;if(!(i&1))out[i/2]=v<<4;else out[i/2]|=v;}return 1;}
static void digest(const unsigned char*p,unsigned n,unsigned char*out){Sha s;char h[65];sha_init(&s);sha_update(&s,p,n);sha_final(&s,h);hex(h,out);}
static int safe(const char*s,unsigned max){unsigned n=strlen(s);if(!n||n>max)return 0;for(unsigned i=0;i<n;i++)if((unsigned char)s[i]<32||(unsigned char)s[i]>126)return 0;return 1;}
static void namespace_id(char**v,unsigned char*out){
 Sha s;char h[65];sha_init(&s);const char tag[]="a7c-plainftp-v1";sha_update(&s,(const unsigned char*)tag,sizeof(tag));
 for(unsigned i=2;i<=5;i++){unsigned n=strlen(v[i]);unsigned char len[4]={n>>24,n>>16,n>>8,n};sha_update(&s,len,4);sha_update(&s,(const unsigned char*)v[i],n);}sha_final(&s,h);hex(h,out);
}
static int password(char*p){unsigned n=0;while(n<256){char c;int r=read(0,&c,1);if(r<0&&errno==EINTR)continue;if(r!=1)return 0;if(c=='\n'){p[n]=0;return n>0;}if((unsigned char)c<32||c==127)return 0;p[n++]=c;}return 0;}
static int login(char**v,unsigned port){
 char secret[257];if(!password(secret))return -1;int fd=connect_ip(v[2],port);if(fd<0){memset(secret,0,sizeof(secret));return -1;}
 int ok=reply(fd)==220;int code=ok?command(fd,"USER",v[4]):-1;
 if(code==331)code=command(fd,"PASS",secret);memset(secret,0,sizeof(secret));
 if(code!=230||command(fd,"TYPE","I")!=200||command(fd,"CWD",v[5])!=250){close(fd);return -1;}return fd;
}
static int passive(int fd,const char*ip){
 int code=command(fd,"EPSV","");unsigned port=0;
 if(code==229){char*p=strchr(response,'(');if(!p)return -1;char d=p[1];if(!d||p[2]!=d||p[3]!=d)return -1;p+=4;char digits[6];unsigned n=0;while(*p>='0'&&*p<='9'&&n<5)digits[n++]=*p++;digits[n]=0;u64 x;if(*p!=d||p[1]!=')'||!decimal(digits,&x)||!x||x>65535)return -1;port=x;}
 else if(code==500||code==502||code==522){
  if(command(fd,"PASV","")!=227)return -1;char*p=strchr(response,'(');unsigned a,b,c,d,h,l;char end;
  if(!p||sscanf(p,"(%u,%u,%u,%u,%u,%u%c",&a,&b,&c,&d,&h,&l,&end)!=7||end!=')'||a>255||b>255||c>255||d>255||h>255||l>255)return -1;
  port=h*256+l;if(!port)return -1;
 }else return -1;
 /* Always use the authenticated control host, not a PASV-supplied address. */
 return connect_ip(ip,port);
}
static int size_of(int fd,const char*name,u64*size){
 int code=command(fd,"SIZE",name);if(code==550)return 0;if(code!=213)return -1;
 char*p=strchr(response,'\r');if(!p)return -1;*p=0;return decimal(response+4,size)?1:-1;
}
/* 550 is ambiguous (missing or inaccessible). Before treating it as missing,
 * obtain a successful full MLSD listing; any same-name entry is a conflict. */
static int absent(int fd,const char*ip,const char*name){
 int data=passive(fd,ip);if(data<0)return 0;int code=command(fd,"MLSD","");if(code!=125&&code!=150){close(data);return 0;}
 char row[2048];unsigned n=0,total=0;int found=0;u32 t=millis();
 for(;;){if(!ready(data,1,t)){close(data);return 0;}int count=read(data,block,sizeof(block));if(count<0&&(errno==EAGAIN||errno==EINTR))continue;if(count<0){close(data);return 0;}if(!count)break;t=millis();total+=count;if(total>1048576){close(data);return 0;}
  for(int i=0;i<count;i++){if(!block[i]||n>=sizeof(row)-1){close(data);return 0;}row[n++]=block[i];if(block[i]=='\n'){row[n]=0;if(n<2||row[n-2]!='\r'){close(data);return 0;}row[n-2]=0;char*p=strchr(row,' ');if(!p||p==row){close(data);return 0;}if(!strcmp(p+1,name))found=1;n=0;}}
 }close(data);code=reply(fd);return !n&&!found&&(code==226||code==250);
}
static int upload(int fd,const char*ip,const char*part,const char*final,u64 expected,const char*source){
 u64 size=0;int exists=size_of(fd,final,&size);if(exists<0)return 75;
 if(exists==1&&size!=expected)return 90;
 if(!exists&&!absent(fd,ip,final))return 90;
 /* Existing final is never overwritten: drain source, then commit confirms its length.
  * An owned .part may be replaced on retry; one writer per namespace required. */
 int data=-1;
 if(!exists){data=passive(fd,ip);if(data<0)return 75;int code=command(fd,"STOR",part);if(code!=125&&code!=150){close(data);return 75;}}
 int in=open(source,O_RDONLY|O_NONBLOCK);if(in<0){if(data>=0)close(data);return 75;}
 struct upload_progress progress;progress_begin(&progress);progress_publish(&progress,exists?expected:0,expected);
 u64 total=0;u32 t=millis();
 while(total<expected&&!expired()){
  int n=read(in,block,sizeof(block));if(n>0){total+=(unsigned)n;t=millis();if(total>expected||(!exists&&!send_all(data,block,n))){close(in);if(data>=0)close(data);return 75;}progress_publish(&progress,exists?expected:total,expected);}
  else if(n<0&&errno!=EAGAIN&&errno!=EINTR){close(in);if(data>=0)close(data);return 75;}
  else {if(millis()-t>30000){close(in);if(data>=0)close(data);return 75;}usleep(10000);}
 }
 close(in);if(data>=0){close(data);int code=reply(fd);if(code!=226&&code!=250)return 75;}
 if(total!=expected||expired())return 75;
 return size_of(fd,exists?final:part,&size)==1&&size==expected?0:75;
}
int main(int argc,char**v){
 if(argc<6)return 64;u64 port;
 if(!safe(v[2],15)||inet_addr(v[2])==0xffffffffU||!decimal(v[3],&port)||!port||port>65535||v[3][0]=='0'||!safe(v[4],128)||!safe(v[5],400)||v[5][0]!='/'||strstr(v[5],"/../")||strstr(v[5],"/./")||strstr(v[5],"//"))return 64;
 if(argc==6&&!strcmp(v[1],"namespace")){unsigned char id[32];namespace_id(v,id);const char h[]="0123456789abcdef";char out[65];for(unsigned i=0;i<32;i++){out[i*2]=h[id[i]>>4];out[i*2+1]=h[id[i]&15];}out[64]='\n';return write(1,out,65)==65?0:74;}
 if(argc==6&&(!strcmp(v[1],"check")||!strcmp(v[1],"check-fast"))){
  owner=getppid();began=millis();limit=!strcmp(v[1],"check-fast")?1000:4000;
  signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
  int fd=login(v,port);if(fd<0)return 75;
  int rc=command(fd,"NOOP","")==200?0:75;close(fd);return rc;
 }
 if(argc==7&&!strcmp(v[1],"slot")){
  unsigned char id[32],destination[32];if(!hex(v[6],id))return 64;
  namespace_id(v,destination);Sha s;char out[65];sha_init(&s);
  const char tag[]="a7c-receipt-slot-v1";sha_update(&s,(const unsigned char*)tag,sizeof(tag));
  sha_update(&s,destination,32);sha_update(&s,id,32);sha_final(&s,out);
  for(unsigned i=0;i<6;i++)if(out[i]>='a'&&out[i]<='f')out[i]-=32;
  out[6]='\n';return write(1,out,7)==7?0:74;
 }
 if(argc==7&&!strcmp(v[1],"armed")){
  unsigned char id[32];if(!hex(v[6],id))return 64;
  owner=getppid();began=millis();limit=8000;signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
  int fd=login(v,port);if(fd<0)return 75;char trigger[80];snprintf(trigger,sizeof(trigger),".a7c-start-%s",v[6]);u64 n=0;
  int rc=size_of(fd,trigger,&n)==1&&n==1?0:75;close(fd);return rc;
 }
 if((argc==10&&(!strcmp(v[1],"match")||!strcmp(v[1],"match-row")))||(argc==11&&!strcmp(v[1],"rekey"))){
  A7cReceipt expected;memset(&expected,0,sizeof(expected));
  if(!hex(v[6],expected.identity)||!decimal(v[7],&expected.bytes)||!expected.bytes)return 64;
  namespace_id(v,expected.destination);char final[80];snprintf(final,sizeof(final),"%s.MP4",v[6]);digest((const unsigned char*)final,strlen(final),expected.remote_path);
  unsigned char data[2][513];A7cReceiptSlot slots[2];memset(slots,0,sizeof(slots));
  for(unsigned i=0;i<2;i++){if(!strcmp(v[8+i],"-"))continue;int fd=open(v[8+i],O_RDONLY);if(fd<0)return 90;unsigned n=0;while(n<513){int got=read(fd,data[i]+n,513-n);if(got<0&&errno==EINTR)continue;if(got<0){close(fd);return 90;}if(!got)break;n+=got;}close(fd);slots[i].data=data[i];slots[i].length=n;slots[i].state=A7C_SLOT_READ;}
  /* A migrated receipt keeps its actual prior remote path. Match its full
   * file key, target and length; do not invent a new remote path for old media.
   * The ordinary codec still rejects differing valid A/B destination paths. */
  if(!strcmp(v[1],"match-row"))for(unsigned i=0;i<2;i++){
   A7cReceipt prior;if(slots[i].state==A7C_SLOT_READ&&a7c_receipt_decode(slots[i].data,slots[i].length,&prior)==A7C_RECORD_OK){memcpy(expected.remote_path,prior.remote_path,32);break;}
  }
  int selected,rc=a7c_receipt_recover(slots,&expected,A7C_PROOF_FTP_SIZE,&selected);
  if(!strcmp(v[1],"rekey")){
   A7cReceipt prior;unsigned char record[512];
   if(rc!=A7C_RECEIPT_SKIP||selected<0||a7c_receipt_decode(slots[selected].data,slots[selected].length,&prior)!=A7C_RECORD_OK)return 90;
   if(!hex(v[10],prior.identity))return 64;
   if(a7c_receipt_encode(&prior,record)!=A7C_RECORD_OK)return 90;
   return write(1,record,sizeof record)==sizeof record?0:74;
  }
  return rc==A7C_RECEIPT_SKIP?0:(rc==A7C_RECEIPT_RETRY?10:90);
 }
 int put=!strcmp(v[1],"put"),commit=!strcmp(v[1],"commit");
 if(argc!=10||(!put&&!commit))return 64;
 A7cReceipt receipt;memset(&receipt,0,sizeof(receipt));u64 seconds;
 if(!hex(v[6],receipt.identity)||!decimal(v[7],&receipt.bytes)||!receipt.bytes||receipt.bytes>274877906944ULL||!decimal(v[9],&seconds)||seconds<1||seconds>86400)return 64;
 if(commit&&strcmp(v[8],"-"))return 64;
 owner=getppid();began=millis();limit=(u32)seconds*1000;signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
 char final[80],part[80];snprintf(final,sizeof(final),"%s.MP4",v[6]);snprintf(part,sizeof(part),".%s.part",v[6]);
 int fd=login(v,port);if(fd<0)return 75;
 if(put){int rc=upload(fd,v[2],part,final,receipt.bytes,v[8]);close(fd);return rc;}
 u64 size=0;int exists=size_of(fd,final,&size);int rc=75;
 if(exists<0)goto done;
 if(exists==1){if(size!=receipt.bytes){rc=90;goto done;}}
 else {
  if(!absent(fd,v[2],final)){rc=90;goto done;}
  if(size_of(fd,part,&size)!=1||size!=receipt.bytes)goto done;
  if(command(fd,"RNFR",part)!=350||command(fd,"RNTO",final)!=250)goto done;
  if(size_of(fd,final,&size)!=1||size!=receipt.bytes)goto done;
 }
 namespace_id(v,receipt.destination);digest((const unsigned char*)final,strlen(final),receipt.remote_path);receipt.proof=A7C_PROOF_FTP_SIZE;
 unsigned char record[512];if(a7c_receipt_encode(&receipt,record)){rc=90;goto done;}
 rc=send_all(1,record,sizeof(record))?0:75;
 done:close(fd);return rc;
}

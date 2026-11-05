/* ILCE-7C Wi-Fi diagnostics: read-only, opt-in, installer-paired.
 *
 * Idle cost: one blocked poll() on the socket and a self-pipe; no timer,
 * network traffic or power lease. Wakes only for a connection or a signal.
 * Every request is authenticated with HMAC-SHA256 over a fresh per-process
 * nonce and a strictly increasing sequence, so the paired key never crosses
 * the network and a captured request cannot be replayed. Only private-range
 * peers are served. Fixed verbs run the installed diag.sh; there is no shell,
 * stop, update or keep-awake verb. START only relaunches the installed
 * uploader supervisor when nothing of it is running.
 */
#include "../uploader/compat.h"
#include "../uploader/sha256.h"
#ifdef __arm__
struct sockaddr_in {unsigned short family,port;unsigned int addr;char zero[8];};
extern int fcntl(int,int,...);
extern int socket(int,int,int),bind(int,const void*,unsigned),listen(int,int),accept(int,void*,unsigned*),setsockopt(int,int,int,const void*,unsigned);
extern unsigned short htons(unsigned short);
extern void *memset(void*,int,unsigned),*memcpy(void*,const void*,unsigned);
#define AF_INET 2
#define SOCK_STREAM 1
#define SOL_SOCKET 1
#define SO_REUSEADDR 2
#define FAMILY family
#define ADDRESS addr
#define PORTFIELD port
#define SIGCHLD 17
#define WNOHANG 1
#define F_SETFL 4
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#define FAMILY sin_family
#define ADDRESS sin_addr.s_addr
#define PORTFIELD sin_port
#endif
#ifndef ROOT
#define ROOT "/setting/a7c-diag"
#endif
#ifndef RAM
#define RAM "/setting/a7c-uploader/ram/diag"
#endif
#ifndef SHELL
#define SHELL "/bin/ash"
#endif
#ifndef PORT
#define PORT 21217
#endif
#ifndef ACTION_TIMEOUT_MS
#define ACTION_TIMEOUT_MS 20000
#endif
#define OUTPUT_LIMIT 49152U

static volatile int stop=0;
static int control[2]={-1,-1};
static void notified(int n){int saved=errno;if(n!=SIGCHLD)stop=1;if(control[1]>=0){char b=1;write(control[1],&b,1);}errno=saved;}
static void drain_control(void){char b[64];while(read(control[0],b,sizeof(b))>0){}}
static int nonblock(int fd){return fcntl(fd,F_SETFL,O_NONBLOCK);}
static int sendall(int fd,const char*b,unsigned n){while(n){struct pollfd p={fd,4,0};if(poll(&p,1,3000)<=0)return -1;int k=write(fd,b,n);if(k<0&&(errno==EAGAIN||errno==EINTR))continue;if(k<=0)return -1;b+=k;n-=(unsigned)k;}return 0;}

static int unhex(const char*h,unsigned char*out,unsigned n){
 for(unsigned i=0;i<2*n;i++){unsigned c=(unsigned char)h[i],v;
  if(c>='0'&&c<='9')v=c-'0';else if(c>='a'&&c<='f')v=c-'a'+10;else return 0;
  if(i&1)out[i/2]|=(unsigned char)v;else out[i/2]=(unsigned char)(v<<4);}
 return 1;
}
/* HMAC-SHA256 with a 64-byte key (the paired 64-hex token as ASCII). */
static void hmac(const char key[64],const char*msg,unsigned n,char out[65]){
 unsigned char pad[64],inner[32];char hex[65];Sha s;
 for(unsigned i=0;i<64;i++)pad[i]=(unsigned char)key[i]^0x36;
 sha_init(&s);sha_update(&s,pad,64);sha_update(&s,(const unsigned char*)msg,n);sha_final(&s,hex);unhex(hex,inner,32);
 for(unsigned i=0;i<64;i++)pad[i]=(unsigned char)key[i]^0x5c;
 sha_init(&s);sha_update(&s,pad,64);sha_update(&s,inner,32);sha_final(&s,out);
}
/* Network byte order address: accept 10/8, 172.16/12, 192.168/16, 127/8. */
static int private_peer(u32 a){
 const unsigned char*b=(const unsigned char*)&a;
 return b[0]==10||b[0]==127||(b[0]==172&&(b[1]&0xf0)==16)||(b[0]==192&&b[1]==168);
}
static int run(int listener,const char*verb){
 int child=fork();if(child<0)return 98;
 if(!child){
  close(control[0]);close(control[1]);close(listener);
  int f=open(RAM "/action.out",O_WRONLY|O_CREAT|O_TRUNC,0600);if(f<0)_exit(98);
  int in=open("/dev/null",O_RDONLY);if(in<0)_exit(98);
  dup2(in,0);dup2(f,1);dup2(f,2);close(in);close(f);
  char*a[]={SHELL,ROOT "/diag.sh",(char*)verb,0};execv(SHELL,a);_exit(127);
 }
 int st=0;u32 t=millis();
 while(millis()-t<ACTION_TIMEOUT_MS){if(waitpid(child,&st,WNOHANG)==child)return (st&127)?128+(st&127):(st>>8)&255;usleep(20000);}
 kill(child,SIGTERM);waitpid(child,&st,0);return 124;
}
static int verb_allowed(const char*v){return !strcmp(v,"STATUS")||!strcmp(v,"TRACE")||!strcmp(v,"PROBE")||!strcmp(v,"START");}

int main(void){
 char token[66],nonce[33],req[160],reply[192];unsigned char random[16];
 int f=open(ROOT "/token",O_RDONLY);if(f<0)return 65;int n=read(f,token,66);close(f);
 if(n!=65||token[64]!='\n')return 65;
 for(int i=0;i<64;i++)if(!((token[i]>='0'&&token[i]<='9')||(token[i]>='a'&&token[i]<='f')))return 65;
 f=open("/dev/urandom",O_RDONLY);if(f<0)return 66;n=read(f,random,16);close(f);if(n!=16)return 66;
 const char*hx="0123456789abcdef";for(int i=0;i<16;i++){nonce[2*i]=hx[random[i]>>4];nonce[2*i+1]=hx[random[i]&15];}nonce[32]=0;
 if(pipe(control)||nonblock(control[0])<0||nonblock(control[1])<0)return 69;
 signal(SIGPIPE,SIG_IGN);signal(SIGTERM,notified);signal(SIGINT,notified);signal(SIGCHLD,notified);
 int s=socket(AF_INET,SOCK_STREAM,0),one=1;if(s<0)return 67;
 setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));
 struct sockaddr_in addr;memset(&addr,0,sizeof(addr));addr.FAMILY=AF_INET;addr.PORTFIELD=htons(PORT);
 if(bind(s,(void*)&addr,sizeof(addr))||listen(s,2))return 68;
 int pf=open(RAM "/listener.pid",O_WRONLY|O_CREAT|O_TRUNC,0600);
 if(pf>=0){n=snprintf(reply,sizeof(reply),"%d\n",getpid());write(pf,reply,(unsigned)n);close(pf);}
 n=snprintf(reply,sizeof(reply),"DIAG_READY pid=%d port=%d\n",getpid(),PORT);write(1,reply,(unsigned)n);
 unsigned seq=0;
 while(!stop&&access(RAM "/stop",0)&&!access(ROOT "/enabled",0)){
  struct pollfd p[2]={{s,1,0},{control[0],1,0}};
  int ready=poll(p,2,-1);
  if(ready<0){if(errno==EINTR)continue;break;}
  if(p[1].revents)drain_control();
  if(stop||!access(RAM "/stop",0)||access(ROOT "/enabled",0))break;
  if(!(p[0].revents&1)){if(p[0].revents)break;continue;}
  struct sockaddr_in peer;memset(&peer,0,sizeof(peer));unsigned plen=sizeof(peer);
  int c=accept(s,(void*)&peer,&plen);if(c<0)continue;
  if(nonblock(c)<0||!private_peer(peer.ADDRESS)){close(c);continue;}
  n=snprintf(reply,sizeof(reply),"A7CDIAG1 %s %u\n",nonce,seq);
  if(sendall(c,reply,(unsigned)n)){close(c);continue;}
  unsigned used=0;u32 begin=millis();int complete=0;
  while(used<sizeof(req)-1&&millis()-begin<3000){
   struct pollfd q={c,1,0};if(poll(&q,1,200)<=0)continue;
   int k=read(c,req+used,1);if(k<=0)break;if(req[used++]=='\n'){complete=1;break;}
  }
  req[used]=0;
  /* Request: "<VERB> <SEQ> <HMAC>\n", HMAC over "A7CDIAG1 <nonce> <seq> <verb>". */
  char verb[12]={0},mac[65]={0},seqtext[12]={0};unsigned want=0;int valid=complete;
  if(valid){
   char*a=req,*sp1,*sp2;
   for(sp1=a;*sp1&&*sp1!=' ';sp1++);
   if(*sp1!=' '||sp1==a||sp1-a>=(long)sizeof(verb))valid=0;
   else{memcpy(verb,a,(unsigned)(sp1-a));
    for(sp2=sp1+1;*sp2>='0'&&*sp2<='9';sp2++);
    if(*sp2!=' '||sp2==sp1+1||sp2-sp1-1>9)valid=0;
    else{memcpy(seqtext,sp1+1,(unsigned)(sp2-sp1-1));want=(unsigned)atoi(seqtext);
     if(strlen(sp2+1)!=65||sp2[65]!='\n')valid=0;else memcpy(mac,sp2+1,64);}}
  }
  valid=valid&&verb_allowed(verb)&&want==seq+1&&seqtext[0]!='0';
  if(valid){
   char msg[96],expected[65];unsigned diff=0;
   n=snprintf(msg,sizeof(msg),"A7CDIAG1 %s %u %s",nonce,want,verb);
   hmac(token,msg,(unsigned)n,expected);
   for(int i=0;i<64;i++)diff|=(unsigned char)expected[i]^(unsigned char)mac[i];
   valid=!diff;
  }
  if(!valid){sendall(c,"REJECTED\n",9);close(c);continue;}
  seq=want;
  int rc=run(s,verb);
  n=snprintf(reply,sizeof(reply),"RESULT %u %s %d\n",seq,verb,rc);
  if(!sendall(c,reply,(unsigned)n)){
   f=open(RAM "/action.out",O_RDONLY);
   if(f>=0){char b[1024];unsigned total=0;while((n=read(f,b,sizeof(b)))>0&&total+(unsigned)n<=OUTPUT_LIMIT){total+=(unsigned)n;if(sendall(c,b,(unsigned)n))break;}close(f);}
  }
  close(c);
 }
 close(s);close(control[0]);close(control[1]);unlink(RAM "/listener.pid");
 n=snprintf(reply,sizeof(reply),"DIAG_EXIT stop=%d\n",stop);write(1,reply,(unsigned)n);
 return 0;
}

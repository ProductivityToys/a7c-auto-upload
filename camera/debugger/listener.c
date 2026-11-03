/* Idle listener: no polling traffic and no idle power lease. NAS peer + token,
 * fresh per-process nonce and monotonic command sequence; fixed actions only. */
#include "../uploader/compat.h"
#ifdef __arm__
struct sockaddr_in {unsigned short family,port;unsigned int addr;char zero[8];};
extern int fcntl(int,int,...);
extern int socket(int,int,int),bind(int,const void*,unsigned),listen(int,int),accept(int,void*,unsigned*),setsockopt(int,int,int,const void*,unsigned),sscanf(const char*,const char*,...);
extern unsigned short htons(unsigned short);
extern unsigned int inet_addr(const char*);
#define AF_INET 2
#define SOCK_STREAM 1
#define SOL_SOCKET 1
#define SO_REUSEADDR 2
#define FAMILY family
#define ADDRESS addr
#define PORTFIELD port
#define SIGCHLD 17
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#define FAMILY sin_family
#define ADDRESS sin_addr.s_addr
#define PORTFIELD sin_port
#endif
#ifndef ROOT
#define ROOT "/setting/a7c-debug"
#endif
#ifndef RAM
#define RAM "/setting/a7c-debug/ram"
#endif
#ifndef TOKEN
#define TOKEN "/setting/a7c-uploader/token"
#endif
#ifndef SHELL
#define SHELL "/bin/ash"
#endif
#ifndef PEER
#define PEER "192.168.5.190"
#endif
#ifndef PORT
#define PORT 21216
#endif
#ifndef ACTION_TIMEOUT_MS
#define ACTION_TIMEOUT_MS 20000
#endif
#ifdef MAINTENANCE_SECONDS
/* RAM-only maintenance session. Zero disables session expiry; per-action and
 * power-lease limits remain independent. Positive values use signal shutdown. */
extern unsigned alarm(unsigned);
#endif
static volatile int stop=0,stop_signal=0;
static int control[2]={-1,-1};
/* A self-pipe avoids both idle timer wakeups and the signal-before-poll race.
 * Children must close these descriptors; only this process owns the wakeup. */
static void notified(int n){int saved=errno;if(n!=SIGCHLD){stop=1;stop_signal=n;}if(control[1]>=0){char b=1;write(control[1],&b,1);}errno=saved;}
static void close_control(void){close(control[0]);close(control[1]);}
static void drain_control(void){char b[64];while(read(control[0],b,sizeof(b))>0){} }
static int sendall(int fd,const char*b,unsigned n){while(n){struct pollfd p={fd,4,0};if(poll(&p,1,2000)<=0)return -1;int k=write(fd,b,n);if(k<=0)return -1;b+=k;n-=k;}return 0;}
static int touch(const char*path){int f=open(path,O_WRONLY|O_CREAT|O_TRUNC,0600);if(f<0)return -1;close(f);return 0;}
#ifdef ACTION_TRACE
#ifndef MAINTENANCE_SECONDS
#error ACTION_TRACE is restricted to temporary maintenance builds
#endif
static unsigned trace_sequence;
static int trace_chunk(int client,const char *bytes,unsigned length){
 char header[64];int n=snprintf(header,sizeof(header),"TRACE %u %u\n",trace_sequence,length);
 return sendall(client,header,n)||sendall(client,bytes,length);
}
static void trace_drain(int client,int fd,unsigned *total,int *connected){
 char bytes[1024];int n;
 while(*total<32768U&&(n=read(fd,bytes,sizeof(bytes)))>0){
  if((unsigned)n>32768U-*total)n=(int)(32768U-*total);
  *total+=(unsigned)n;
  if(*connected&&trace_chunk(client,bytes,(unsigned)n))*connected=0;
 }
}
#endif
static int action(int listener,int client,const char*name,const char*arg){
#ifdef ACTION_TRACE
 int trace_fd=-1,connected=1;unsigned total=0;
 if(trace_sequence&&!strcmp(name,"START")){
  int f=open(RAM "/action.out",O_WRONLY|O_CREAT|O_TRUNC,0600);if(f<0)return 98;close(f);
  trace_fd=open(RAM "/action.out",O_RDONLY);if(trace_fd<0)return 98;
  if(trace_chunk(client,"ACTION_BEGIN START\n",19)){close(trace_fd);return 98;}
 }
#endif
 int child=fork();if(child<0){
#ifdef ACTION_TRACE
  if(trace_fd>=0)close(trace_fd);
#endif
  return 98;
 }
 if(!child){
#ifdef ACTION_TRACE
 if(trace_fd>=0)close(trace_fd);
#endif
 close_control();close(listener);close(client);int f=open(RAM "/action.out",O_WRONLY|O_CREAT|O_TRUNC,0600);if(f<0)_exit(98);dup2(f,1);dup2(f,2);close(f);const char *script=ROOT "/action.sh";
#ifdef DISPLAY_TRANSFER_PROTOCOL
 if(name[0]=='X')script=ROOT "/manage.sh";
#endif
 char*a[]={SHELL,(char*)script,(char*)name,(char*)arg,0};execv(SHELL,a);_exit(127);}
 int st=0;u32 t=millis();
 while(millis()-t<ACTION_TIMEOUT_MS){
#ifdef ACTION_TRACE
  if(trace_fd>=0)trace_drain(client,trace_fd,&total,&connected);
#endif
  if(waitpid(child,&st,1)==child){
#ifdef ACTION_TRACE
   if(trace_fd>=0){trace_drain(client,trace_fd,&total,&connected);close(trace_fd);}
#endif
   return (st&127)?128+(st&127):(st>>8)&255;
  }
  usleep(20000);
 }
#ifdef ACTION_TRACE
 if(trace_fd>=0){trace_drain(client,trace_fd,&total,&connected);close(trace_fd);}
#endif
 /* Action script never runs a native copy. Do not kill an ongoing uploader. */
 kill(child,SIGTERM);waitpid(child,&st,0);return 124;
}

#ifdef DISPLAY_TRANSFER_PROTOCOL
#include "../display/transfer_protocol.h"
#endif
int main(void){
 char token[66],nonce[33],req[384],reply[256];unsigned char random[16];
 int f=open(TOKEN,O_RDONLY);if(f<0)return 65;int n=read(f,token,66);close(f);if(n!=65||token[64]!='\n')return 65;token[64]=0;
 f=open("/dev/urandom",O_RDONLY);if(f<0)return 66;n=read(f,random,16);close(f);if(n!=16)return 66;
 const char*hex="0123456789abcdef";for(int i=0;i<16;i++){nonce[2*i]=hex[random[i]>>4];nonce[2*i+1]=hex[random[i]&15];}nonce[32]=0;
 if(pipe(control))return 69;
 for(int i=0;i<2;i++){
#ifdef __arm__
  if(fcntl(control[i],4,2048)<0)return 69;
#else
  if(fcntl(control[i],F_SETFL,O_NONBLOCK)<0)return 69;
#endif
 }
 signal(SIGPIPE,SIG_IGN);signal(SIGTERM,notified);signal(SIGINT,notified);signal(SIGCHLD,notified);
#ifdef MAINTENANCE_SECONDS
 signal(14,notified);alarm(MAINTENANCE_SECONDS);
#endif
 int s=socket(AF_INET,SOCK_STREAM,0),one=1;if(s<0)return 67;setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));
 struct sockaddr_in addr={0};addr.FAMILY=AF_INET;addr.PORTFIELD=htons(PORT);
 if(bind(s,(void*)&addr,sizeof(addr))||listen(s,3))return 68;
 int pid=open(RAM "/listener.pid",O_WRONLY|O_CREAT|O_TRUNC,0600);if(pid>=0){n=snprintf(reply,sizeof(reply),"%d\n",getpid());write(pid,reply,n);close(pid);}
#ifdef MAINTENANCE_SECONDS
 n=snprintf(reply,sizeof(reply),"LISTENER_READY pid=%d expiry_seconds=%u\n",getpid(),(unsigned)MAINTENANCE_SECONDS);write(1,reply,n);
#endif
 unsigned seq=0;int lease=0;
 while(!stop && access(RAM "/stop",0) && !access(ROOT "/enabled",0)){
  if(lease){int st;if(waitpid(lease,&st,1)==lease)lease=0;}
  struct pollfd p[2]={{s,1,0},{control[0],1,0}};
  int ready=poll(p,2,-1);
  if(ready<0){if(errno==EINTR)continue;break;}
  if(p[1].revents)drain_control();
  if(stop || !access(RAM "/stop",0) || access(ROOT "/enabled",0))break;
  if(!(p[0].revents&1)){if(p[0].revents)break;continue;}
  struct sockaddr_in peer={0};unsigned plen=sizeof(peer);int c=accept(s,(void*)&peer,&plen);if(c<0)continue;
  #ifdef __arm__
  fcntl(c,4,2048);
#else
  fcntl(c,F_SETFL,O_NONBLOCK);
#endif
  if(peer.ADDRESS!=inet_addr(PEER)){close(c);continue;}
  n=snprintf(reply,sizeof(reply),"A7CDBG2 %s %u\n",nonce,seq);if(sendall(c,reply,n)){close(c);continue;}
  unsigned used=0;u32 begin=millis();int complete=0;
  while(used<sizeof(req)-1 && millis()-begin<3000){struct pollfd q={c,1,0};if(poll(&q,1,100)<=0)continue;int k=read(c,req+used,1);if(k<=0)break;if(req[used++]=='\n'){complete=1;break;}}
  req[used]=0;char auth[65]={0},session[33]={0},verb[16]={0},arg[192]={0},extra[2]={0};unsigned want=0;arg[0]=0;
  int fields=sscanf(req,"AUTH %64s %32s %u %15s %191s %1s",auth,session,&want,verb,arg,extra);
  unsigned diff=0;int valid=complete&&(fields==4||fields==5)&&strlen(auth)==64;
  if(valid)for(int i=0;i<64;i++)diff|=(unsigned char)auth[i]^(unsigned char)token[i];
  valid=valid&&!diff&&!strcmp(session,nonce)&&want==seq+1&&want<1000000000;
  int update=!strcmp(verb,"UPDATE");
#ifdef DISPLAY_TRANSFER_PROTOCOL
  int transfer=display_transfer_verb(verb);
  if(transfer){if(!display_transfer_valid(verb,arg,fields))valid=0;}
  else
#endif
  if(update){if(fields!=5||strlen(arg)!=64)valid=0;else for(int i=0;i<64;i++)if(!((arg[i]>='a'&&arg[i]<='f')||(arg[i]>='0'&&arg[i]<='9')))valid=0;}
  else if(fields!=4)valid=0;
  if(strcmp(verb,"STATUS")&&strcmp(verb,"TRACE")&&strcmp(verb,"PROBE")&&strcmp(verb,"START")&&strcmp(verb,"PAUSE")&&strcmp(verb,"HOLD")&&strcmp(verb,"RELEASE")&&strcmp(verb,"EXIT")&&!update
#ifdef DISPLAY_TRANSFER_PROTOCOL
     &&!transfer
#endif
#ifdef ACTION_TRACE
     &&strcmp(verb,"START_TRACE")
#endif
     )valid=0;
#ifdef DISPLAY_OBSERVER_ONLY
  /* Temporary display observer reuses authentication, never uploader controls. */
#ifdef DISPLAY_BLINK_CONTROL
  /* PAUSE only writes the display worker's cancellation marker. */
  if(strcmp(verb,"STATUS")&&strcmp(verb,"PROBE")&&strcmp(verb,"PAUSE")
#ifdef DISPLAY_TRANSFER_PROTOCOL
     &&!transfer
#endif
#ifdef ACTION_TRACE
     &&strcmp(verb,"START_TRACE")
#endif
     )valid=0;
#else
  if(strcmp(verb,"STATUS")&&strcmp(verb,"PROBE"))valid=0;
#endif
#endif
  if(!valid){sendall(c,"REJECTED\n",9);close(c);continue;}
  seq=want;int rc=0;
#ifdef DISPLAY_TRANSFER_PROTOCOL
  if(transfer){display_transfer(s,c,seq,verb,arg);close(c);continue;}
#endif
  if(!strcmp(verb,"HOLD")){
   if(lease)rc=1;
   else {unlink(RAM "/lease.ready");unlink(RAM "/lease.done");lease=fork();
    if(!lease){close_control();close(s);close(c);int out=open(RAM "/lease.log",O_WRONLY|O_CREAT|O_TRUNC,0600);if(out<0)_exit(98);dup2(out,1);dup2(out,2);close(out);char*a[]={RAM "/lease","--upload-lease","600",0};execv(a[0],a);_exit(127);}
    if(lease<0){lease=0;rc=98;}
   }
  }else if(!strcmp(verb,"RELEASE"))rc=touch(RAM "/lease.done")?98:0;
  else if(!strcmp(verb,"EXIT")){
#ifndef MAINTENANCE_SECONDS
   rc=action(s,c,"PAUSE","");
#endif
   touch(RAM "/lease.done");unlink(ROOT "/enabled");stop=1;
  }
#ifdef ACTION_TRACE
  else if(!strcmp(verb,"START_TRACE")){
   trace_sequence=seq;rc=action(s,c,"START","");trace_sequence=0;
  }
#endif
  else if(strcmp(verb,"STATUS"))rc=action(s,c,verb,arg);
  n=snprintf(reply,sizeof(reply),"RESULT %u %s %d\n",seq,verb,rc);sendall(c,reply,n);
  /* Return a fresh bounded snapshot after every operation; no media queries. */
  int drc=!strcmp(verb,"TRACE")?rc:action(s,c,"STATUS","");
  if(!drc){f=open(RAM "/action.out",O_RDONLY);if(f>=0){unsigned total=0;char b[1024];while((n=read(f,b,sizeof(b)))>0&&total+(unsigned)n<=32768){total+=n;if(sendall(c,b,n))break;}close(f);}}
  close(c);
 }
#ifdef MAINTENANCE_SECONDS
 n=snprintf(reply,sizeof(reply),"LISTENER_EXIT signal=%d stop_file=%d enabled=%d\n",stop_signal,!access(RAM "/stop",0),!access(ROOT "/enabled",0));write(1,reply,n);
#endif
 touch(RAM "/lease.done");close(s);close_control();return 0;
}

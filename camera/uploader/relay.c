/* Native IFSYS -> source FIFO -> bounded relay -> FTP FIFO.
 * Ordinary FTP builds use RELAY_SIZE_ONLY: count bytes, no video-body hash.
 * The historical receiver build retains its source-digest protocol.
 * On broken network continue draining source. An independent reader guardian
 * takes over if relay exits unexpectedly, so the native writer retains a reader.
 * Never signals the native firmware task; no media device access.
 */
#include "compat.h"
#ifndef RELAY_SIZE_ONLY
#include "sha256.h"
#endif
static unsigned char buffer[65536];
static char ready[256],done[256],guarddone[256],result[256];
static void mark(const char*p,const char*s){int fd=open(p,O_WRONLY|O_CREAT|O_TRUNC,0600);if(fd>=0){write(fd,s,strlen(s));close(fd);}}
static void guardian(int source,int control){
 signal(SIGTERM,SIG_IGN);signal(SIGINT,SIG_IGN);struct pollfd p={control,1,0};char c=0;
 while(1){int rc=poll(&p,1,1000);if(rc>0){int n=read(control,&c,1);if(n==1&&c=='D'){close(source);mark(guarddone,"normal\n");_exit(0);}if(n==0)break;}else if(rc<0&&errno!=EINTR)break;}
 /* Wait for native completion marker when the owner died before any data.
  * If the whole worker crashed before issuing copy, this harmless RAM reader
  * remains until next boot; it owns no power lease and performs no media I/O. */
 int seen=0;
 for(;;){int n=read(source,buffer,sizeof(buffer));if(n>0){seen=1;continue;}else if(n==0&&(seen||access(done,0)==0))break;else if(n<0&&errno!=EAGAIN&&errno!=EINTR)break;usleep(10000);}
 close(source);mark(guarddone,"recovered\n");_exit(0);
}
int main(int argc,char**argv){
 if(argc!=3)return 64;
#ifdef __arm__
 if(strcmp(argv[1],"/setting/a7c-uploader/ram"))return 64;
#endif
 char*end=0;u64 expected=strtoull(argv[2],&end,10);if(!end||*end||!expected||expected>274877906944ULL)return 64;
 char sourcepath[256],netpath[256];
 if(strlen(argv[1])>180)return 64;
 snprintf(sourcepath,sizeof(sourcepath),"%s/source.fifo",argv[1]);snprintf(netpath,sizeof(netpath),"%s/network.fifo",argv[1]);
 snprintf(ready,sizeof(ready),"%s/relay.ready",argv[1]);snprintf(done,sizeof(done),"%s/copy.done",argv[1]);snprintf(guarddone,sizeof(guarddone),"%s/guard.done",argv[1]);snprintf(result,sizeof(result),"%s/relay.result",argv[1]);
 signal(SIGPIPE,SIG_IGN);
 int src=open(sourcepath,O_RDONLY|O_NONBLOCK);if(src<0)return 65;
 int p[2];if(pipe(p))return 66;int guard=fork();if(guard<0)return 67;
 if(!guard){close(p[1]);guardian(src,p[0]);}
 close(p[0]);int net=-1;u32 started=millis();
 while(millis()-started<10000){net=open(netpath,O_WRONLY|O_NONBLOCK);if(net>=0)break;usleep(50000);}
 if(net<0){
  /* No ready marker means the worker has not submitted native copy. Finish
   * our guardian here instead of leaving its asynchronous empty drain to
   * race the worker's FIFO cleanup after a failed FTP login/connect. */
  write(p[1],"D",1);close(p[1]);close(src);
  int status=0;while(waitpid(guard,&status,0)<0&&errno==EINTR){}
  return 68;
 }
 mark(ready,"ready\n");
#ifndef RELAY_SIZE_ONLY
 Sha hash;sha_init(&hash);
#endif
 u64 total=0;int failed=0,seen=0;u32 progress=millis();
 for(;;){
  int n=read(src,buffer,sizeof(buffer));
  if(n>0){seen=1;total+=(unsigned)n;
#ifndef RELAY_SIZE_ONLY
   sha_update(&hash,buffer,(unsigned)n);
#endif
   progress=millis();if(total>expected)failed=1;
   unsigned off=0;u32 sent=millis();
   while(!failed&&off<(unsigned)n){int w=write(net,buffer+off,(unsigned)n-off);if(w>0){off+=(unsigned)w;sent=millis();}else if(w<0&&(errno==EAGAIN||errno==EINTR)){if(millis()-sent>=30000){failed=1;break;}struct pollfd f={net,4,0};poll(&f,1,100);}else failed=1;}
   if(failed&&net>=0){close(net);net=-1;}
  }else if(n==0&&(seen||access(done,0)==0))break;
  else if(n<0&&errno!=EAGAIN&&errno!=EINTR){failed=1;break;}
  else {if(millis()-progress>30000&&!failed){failed=1;if(net>=0){close(net);net=-1;}}if(n<0){struct pollfd f={src,1,0};poll(&f,1,100);}else usleep(10000);}
 }
 if(net>=0)close(net);
 if(total!=expected)failed=1;
 char line[160];
#ifdef RELAY_SIZE_ONLY
 snprintf(line,sizeof(line),"%d %llu\n",failed,total);
#else
 char hex[65];sha_final(&hash,hex);snprintf(line,sizeof(line),"%d %llu %s\n",failed,total,hex);
#endif
 mark(result,line);
 write(p[1],"D",1);close(p[1]);close(src);int status=0;waitpid(guard,&status,0);return failed||status?69:0;
}

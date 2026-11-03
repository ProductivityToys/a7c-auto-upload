/* ILCE-7C 2.00: read-only command whitelist, fresh reply framing, prompt-driven exit.
 * Only native IFSYS reads to owned tmpfs destinations. No raw media device opens.
 */
typedef unsigned int u32;
extern int pipe(int*),fork(void),dup2(int,int),close(int),execv(const char*,char*const*),kill(int,int),waitpid(int,int*,int),fcntl(int,int,...),poll(void*,unsigned long,int),read(int,void*,unsigned),write(int,const void*,unsigned),strcmp(const char*,const char*),strncmp(const char*,const char*,unsigned),snprintf(char*,unsigned,const char*,...),atoi(const char*),clock_gettime(int,void*),usleep(unsigned);
extern int access(const char*,int);
extern unsigned strlen(const char*); extern char *strstr(const char*,const char*);extern void _exit(int);
extern void (*signal(int,void (*)(int)))(int);
struct pf {int fd;short events,revents;};struct ts {long sec,nsec;};
#ifndef A7C_MONOTONIC_CLOCK
#define A7C_MONOTONIC_CLOCK 1
#endif
static u32 ms(void){struct ts t;if(clock_gettime(A7C_MONOTONIC_CLOCK,&t))_exit(74);return (u32)t.sec*1000+(u32)t.nsec/1000000;}
static int letter(const char*s){return s[0]>='A'&&s[0]<='Z'&&!s[1];}
static int name(const char*s){if(s[0]!='C')return 0;for(int i=1;i<5;i++)if(s[i]<'0'||s[i]>'9')return 0;return !strcmp(s+5,".MP4")||!strcmp(s+5,"M01.XML");}
#ifdef SD_RECEIPT_MODE
static int receipt_name(const char*s){if(strlen(s)!=12||s[0]!='U'||(s[7]!='A'&&s[7]!='B')||strcmp(s+8,".RCP"))return 0;for(int i=1;i<7;i++)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='A'&&s[i]<='F')))return 0;return 1;}
#endif
#include "monitor_result.h"
static char buf[262144],transcript[262144];
/* Fixed transactions reuse one MWF frontend. Each step still
 * requires its own native CRLF echo and following prompt; no pipelining. */
static int filesystem_command(int stage,const char *reply,char *cmd,unsigned cap){
 if(stage==0){snprintf(cmd,cap,"IFSYS getdriveletter /dev/mmca");return 0;}
 if(stage==1){
  const char *p=strstr(reply,"driveLetter = '");
  if(!p||strstr(p+1,"driveLetter = '"))return 74;
  p+=15;if(*p<'A'||*p>'Z'||p[1]!='\'')return 74;
  snprintf(cmd,cap,"IFSYS dir %c:/PRIVATE/M4ROOT/CLIP",*p);return 0;
 }
 if(stage==2){snprintf(cmd,cap,"IFSYS info");return 0;}
 return 64;
}
#ifndef A7C_READY_DIR
#define A7C_READY_DIR "/setting/a7c-uploader/ram"
#endif
#ifndef A7C_READY_LEASE_MS
#define A7C_READY_LEASE_MS 8000U
#define A7C_READY_RELAY_MS 12000U
#endif
static int wait_ready(const char *kind,const char *pid_text){
 const char *path;u32 limit;
 if(!strcmp(kind,"lease")){path=A7C_READY_DIR "/lease.ready";limit=A7C_READY_LEASE_MS;}
 else if(!strcmp(kind,"relay")){path=A7C_READY_DIR "/relay.ready";limit=A7C_READY_RELAY_MS;}
 else return 64;
 unsigned pid=0,n=0;
 for(const char *p=pid_text;*p;p++){if(*p<'0'||*p>'9'||++n>9)return 64;pid=pid*10+(unsigned)(*p-'0');}
 if(pid<=1||pid>2147483647U)return 64;
 u32 start=ms();
 do{
  if(kill((int)pid,0))return 72;
  if(!access(path,0))return 0;
  usleep(100000);
 }while(ms()-start<limit);
 return 124;
}
int main(int argc,char **argv){
 if(argc==4&&!strcmp(argv[1],"wait-ready"))return wait_ready(argv[2],argv[3]);
 signal(13,(void (*)(int))1); /* broken frontend pipe must not terminate helper */
 char cmd[400],native_marker[404];const char *bin="/usr/bin/mwf_monio.elf",*prompt="MWF>",*marker=0;int seconds=8,is_copy=0,batch=0,batch_stage=0,batch_last=2;unsigned transcript_used=0;
#if defined(SD_RECEIPT_MODE)
 if(argc==3&&!strcmp(argv[1],"root")&&letter(argv[2])){snprintf(cmd,sizeof(cmd),"IFSYS dir %s:/",argv[2]);marker=cmd;}
 else if(argc==3&&!strcmp(argv[1],"context")&&letter(argv[2])){batch=4;batch_last=1;snprintf(cmd,sizeof(cmd),"IFSYS info");marker=cmd;}
 else if(argc==4&&letter(argv[2])&&receipt_name(argv[3])&&!strcmp(argv[1],"read")){is_copy=1;snprintf(cmd,sizeof(cmd),"IFSYS cp %s:/%s /setting/a7c-uploader/ram/receipt.read",argv[2],argv[3]);marker=cmd;}
 else if(argc==4&&letter(argv[2])&&receipt_name(argv[3])&&!strcmp(argv[1],"write-verify")){batch=5;batch_last=1;is_copy=1;snprintf(cmd,sizeof(cmd),"IFSYS cp /setting/a7c-uploader/ram/receipt.write %s:/%s",argv[2],argv[3]);marker=cmd;}
 else if(argc==4&&letter(argv[2])&&receipt_name(argv[3])&&!strcmp(argv[1],"write")){is_copy=1;snprintf(cmd,sizeof(cmd),"IFSYS cp /setting/a7c-uploader/ram/receipt.write %s:/%s",argv[2],argv[3]);marker=cmd;}
 else return 64;
#elif defined(DEBUG_STATE_ONLY)
 if(argc==2&&!strcmp(argv[1],"full-info")){bin="/usr/bin/mpr_monio.elf";prompt="MON>";marker="MprIf Debug Information";snprintf(cmd,sizeof(cmd),"MPR Debug Info");}else return 64;
#else
 if(argc==2&&!strcmp(argv[1],"filesystem")){batch=1;filesystem_command(0,"",cmd,sizeof cmd);marker=cmd;}
 else if(argc==2&&!strcmp(argv[1],"recording-bundle")){batch=2;bin="/usr/bin/mpr_monio.elf";prompt="MON>";marker="[MprMcmd][RecInfo] =====";snprintf(cmd,sizeof cmd,"MPR Debug RecInfo");}
 else if(argc==4&&!strcmp(argv[1],"prepare")&&letter(argv[2])&&name(argv[3])&&strstr(argv[3],"M01.XML")){
  batch=3;batch_last=1;is_copy=1;seconds=10;
  snprintf(cmd,sizeof cmd,"IFSYS cp %s:/PRIVATE/M4ROOT/CLIP/%s /setting/a7c-uploader/ram/metadata.xml",argv[2],argv[3]);marker=cmd;
 }
 else if(argc==2&&!strcmp(argv[1],"recording")){bin="/usr/bin/mpr_monio.elf";prompt="MON>";marker="[MprMcmd][RecInfo] =====";snprintf(cmd,sizeof(cmd),"MPR Debug RecInfo");}
 else if(argc==2&&!strcmp(argv[1],"full-info")){bin="/usr/bin/mpr_monio.elf";prompt="MON>";marker="MprIf Debug Information";snprintf(cmd,sizeof(cmd),"MPR Debug Info");}
 else if(argc==2&&!strcmp(argv[1],"drive")){marker="driveLetter =";snprintf(cmd,sizeof(cmd),"IFSYS getdriveletter /dev/mmca");}
 else if(argc==2&&!strcmp(argv[1],"info")){marker="******** Fsys - IFSYS";snprintf(cmd,sizeof(cmd),"IFSYS info");}
 else if(argc==3&&!strcmp(argv[1],"dir")&&letter(argv[2])){snprintf(cmd,sizeof(cmd),"IFSYS dir %s:/PRIVATE/M4ROOT/CLIP",argv[2]);marker=cmd;}
 else if(argc==5&&!strcmp(argv[1],"copy")&&letter(argv[2])&&name(argv[3])){
  is_copy=1;seconds=atoi(argv[4]);if(seconds<10||seconds>86400)return 64;
  const char *out=strstr(argv[3],".MP4")?"source.fifo":"metadata.xml";
  snprintf(cmd,sizeof(cmd),"IFSYS cp %s:/PRIVATE/M4ROOT/CLIP/%s /setting/a7c-uploader/ram/%s",argv[2],argv[3],out);marker=cmd;
 }else return 64;
#endif
#ifdef A7C_TEST_FRONTEND
 bin=A7C_TEST_FRONTEND;
#endif
 /* The frontend echoes typed characters with LF; the firmware echoes the
  * submitted command with CRLF. An older prompt may arrive after local echo.
  * Only the firmware echo can frame directory/copy completion. */
 if(marker==cmd){snprintf(native_marker,sizeof(native_marker),"%s\r\n",cmd);marker=native_marker;}
 int in[2],out[2];if(pipe(in)||pipe(out))return 76;int child=fork();if(child<0)return 76;
 if(!child){dup2(in[0],0);dup2(out[1],1);dup2(out[1],2);close(in[0]);close(in[1]);close(out[0]);close(out[1]);char *a[]={(char*)bin,0};execv(bin,a);_exit(127);}
 close(in[0]);close(out[1]);fcntl(out[0],4,2048);struct pf p={out[0],1,0};
 u32 start=ms(),quiet=start;unsigned used=0;int ready=0,rc=70,status=0,submitted=0;
 write(in[1],"\r",1); /* Empty command flushes the native stdio startup banner. */
 /* Drain only initial history. Require actual native mapping banner, then quiet. */
 while(ms()-start<4000){
  if(poll(&p,1,50)>0){int n=read(out[0],buf+used,sizeof(buf)-used-1);if(n>0){used+=(unsigned)n;buf[used]=0;quiet=ms();if(strstr(buf,"Logical  Addr"))ready=1;if(used>sizeof(buf)-4096)goto done;}}
  if(ready&&ms()-quiet>=250)break;
  if(waitpid(child,&status,1)==child)goto closed;
 }
 if(!ready||ms()-quiet<250)goto done;
 used=0;buf[0]=0;submitted=1; /* conservative: even a partial write is unknown */
 if(write(in[1],cmd,strlen(cmd))!=(int)strlen(cmd)||write(in[1],"\r",1)!=1)goto done;start=ms();
 while(ms()-start<(u32)seconds*1000){
  if(poll(&p,1,100)>0){int n=read(out[0],buf+used,sizeof(buf)-used-1);if(n>0){used+=(unsigned)n;buf[used]=0;const char *m=a7c_completed_reply(buf,marker,prompt);if(m){
   rc=a7c_command_result(is_copy,m);
   if(batch&&!rc){
    unsigned length=strlen(cmd);
    if(batch==2){
     char tag[48];int len=snprintf(tag,sizeof tag,"A7C_REC_PART_%d_BEGIN\n",batch_stage);
     if((unsigned)len>=sizeof transcript-transcript_used){rc=71;break;}
     for(int i=0;i<len;i++)transcript[transcript_used++]=tag[i];
    }
    if(length+used+48>=sizeof transcript-transcript_used){rc=71;break;}
    for(unsigned i=0;i<length;i++)transcript[transcript_used++]=cmd[i];
    transcript[transcript_used++]='\n';
    for(unsigned i=0;i<used;i++)transcript[transcript_used++]=buf[i];
    transcript[transcript_used++]='\n';
    if(batch==2){
     char tag[48];int len=snprintf(tag,sizeof tag,"A7C_REC_PART_%d_END\n",batch_stage);
     for(int i=0;i<len;i++)transcript[transcript_used++]=tag[i];
     /* Fast path remains the two native standby lines. Shell validates it
      * again. Otherwise obtain full state bracketed by fresh RecInfo replies. */
     const char *ok="contentType:Movie(XAVC), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY";
     const char *q=strstr(m,ok);
     if(batch_stage==0&&q&&(q=strstr(q+strlen(ok),ok))&&!strstr(q+strlen(ok),ok))batch_last=0;
    }
    if(batch_stage<batch_last){
     ++batch_stage;
     if(batch==1){rc=filesystem_command(batch_stage,m,cmd,sizeof cmd);if(rc)break;snprintf(native_marker,sizeof native_marker,"%s\r\n",cmd);marker=native_marker;}
     else if(batch==2){
      snprintf(cmd,sizeof cmd,"%s",batch_stage==1?"MPR Debug Info":"MPR Debug RecInfo");
      marker=batch_stage==1?"MprIf Debug Information":"[MprMcmd][RecInfo] =====";
     }
#ifdef SD_RECEIPT_MODE
     else if(batch==5){
      /* Read back only after the native write has completed successfully. */
      snprintf(cmd,sizeof cmd,"IFSYS cp %s:/%s /setting/a7c-uploader/ram/receipt.read",argv[2],argv[3]);
      snprintf(native_marker,sizeof native_marker,"%s\r\n",cmd);marker=native_marker;
     }
#endif
     else{
      is_copy=0;snprintf(cmd,sizeof cmd,"IFSYS dir %s:/",argv[2]);
      snprintf(native_marker,sizeof native_marker,"%s\r\n",cmd);marker=native_marker;
     }
     used=0;buf[0]=0;
     if(write(in[1],cmd,strlen(cmd))!=(int)strlen(cmd)||write(in[1],"\r",1)!=1){rc=74;break;}
     start=ms();continue;
    }
   }
   break;
  }if(used>sizeof(buf)-4096){rc=71;break;}}}
  if(waitpid(child,&status,1)==child){rc=72;goto closed;}
 }
 if(rc==70)rc=124;
 done:kill(child,2);for(int i=0;i<20;i++){if(waitpid(child,&status,1)==child)goto closed;usleep(50000);}kill(child,9);waitpid(child,&status,0);
 closed:close(in[1]);close(out[0]);
 /* 76 proves the copy command was never written, even if frontend died. */
 if(!submitted)rc=76;
 /* Emit own command for parsers; only post-drain response is eligible. */
 if(rc){char diag[128];int dl=snprintf(diag,sizeof(diag),"MONITOR rc=%d child_status=%d ready=%d submitted=%d bytes=%u\n",rc,status,ready,submitted,used);write(2,diag,(unsigned)dl);write(2,buf,used);write(2,"\n",1);}
 if(!rc){if(batch){write(1,transcript,transcript_used);}else{write(1,cmd,strlen(cmd));write(1,"\n",1);write(1,buf,used);write(1,"\n",1);}}return rc;
}

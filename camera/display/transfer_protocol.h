/* Display-only binary transport. Included after authenticated listener helpers.
 * Single client, fixed file roles, bounded streaming and SHA-256; no heap use.
 * The regular uploader/debugger protocol never compiles this extension. */
#include "../uploader/sha256.h"
#ifdef __arm__
extern long lseek(int,long,int);
#endif
#define TRANSFER_MAX 65536U
static int display_transfer_verb(const char *v){
 return !strcmp(v,"FRAME")||!strcmp(v,"SCREEN")||!strcmp(v,"PUSH")||!strcmp(v,"REARM")||!strcmp(v,"ROLLBACK")||!strcmp(v,"UPLOAD_ENABLE");
}
static int transfer_role(const char *s){return !strcmp(s,"capture")||!strcmp(s,"action");}
static const char *frame_path(const char *s){
 if(!strcmp(s,"before"))return RAM "/dds-before.raw";
 if(!strcmp(s,"during"))return RAM "/dds-during.raw";
 if(!strcmp(s,"late"))return RAM "/dds-late.raw";
 if(!strcmp(s,"after"))return RAM "/dds-after.raw";
 if(!strcmp(s,"first"))return RAM "/dds-first.raw";
 if(!strcmp(s,"screen"))return RAM "/shooting.raw";
 return 0;
}
static int transfer_spec(const char *arg,char *role,unsigned *size,char *hash){
 char extra[2];
 if(sscanf(arg,"%15[^:]:%u:%64[a-f0-9]%1s",role,size,hash,extra)!=3||
    !transfer_role(role)||!*size||*size>TRANSFER_MAX||strlen(hash)!=64)return 0;
 char canonical[128];snprintf(canonical,sizeof canonical,"%s:%u:%s",role,*size,hash);
 return !strcmp(canonical,arg);
}
static int display_transfer_valid(const char *verb,const char *arg,int fields){
 if(!strcmp(verb,"SCREEN")||!strcmp(verb,"REARM")||!strcmp(verb,"UPLOAD_ENABLE"))return fields==4;
 if(fields!=5)return 0;
 if(!strcmp(verb,"FRAME"))return frame_path(arg)!=0;
 if(!strcmp(verb,"ROLLBACK"))return transfer_role(arg);
 char role[16],hash[65];unsigned size;
 return transfer_spec(arg,role,&size,hash);
}
static void transfer_result(int c,unsigned seq,const char *verb,int rc){
 char b[96];int n=snprintf(b,sizeof b,"RESULT %u %s %d\n",seq,verb,rc);sendall(c,b,n);
}
static int transfer_write(int f,const char *b,unsigned n){
 while(n){int k=write(f,b,n);if(k<=0)return -1;b+=k;n-=k;}return 0;
}
static void display_transfer(int s,int c,unsigned seq,const char *verb,const char *arg){
 int rc=action(s,c,!strcmp(verb,"FRAME")?"XREADLOCK":"XLOCK","");
 if(rc){transfer_result(c,seq,verb,rc);return;}
 if(!strcmp(verb,"PUSH")){
  char role[16],hash[65],actual[65];unsigned size=0;
  if(!transfer_spec(arg,role,&size,hash)){rc=64;goto finish;}
  rc=action(s,c,"XIDLE","");if(rc)goto finish;
  unlink(RAM "/incoming");
  int f=open(RAM "/incoming",O_WRONLY|O_CREAT|O_EXCL,0600);if(f<0){rc=98;goto finish;}
  char b[4096];int n=snprintf(b,sizeof b,"READY %u %u\n",seq,size);
  if(sendall(c,b,n)){close(f);rc=98;goto finish;}
  Sha hashstate;sha_init(&hashstate);unsigned got=0;u32 begin=millis();
  while(got<size && millis()-begin<45000){
   struct pollfd q={c,1,0};int ready=poll(&q,1,500);
   if(ready<0&&errno==EINTR)continue;
   if(ready<0){rc=98;break;}if(!ready)continue;
   unsigned need=size-got;if(need>sizeof b)need=sizeof b;
   n=read(c,b,need);if(n<=0){rc=98;break;}
   if(transfer_write(f,b,(unsigned)n)){rc=98;break;}
   sha_update(&hashstate,(unsigned char*)b,n);got+=(unsigned)n;
  }
  if(close(f))rc=98;
  sha_final(&hashstate,actual);
  if(got!=size||strcmp(hash,actual))rc=98;
  if(!rc&&!strcmp(role,"capture")){
   unsigned char elf[20];int check=open(RAM "/incoming",O_RDONLY);
   int count=check<0?-1:read(check,elf,20);if(check>=0)close(check);
   if(count!=20||elf[0]!=127||elf[1]!='E'||elf[2]!='L'||elf[3]!='F'||
      elf[4]!=1||elf[5]!=1||elf[6]!=1||elf[16]!=2||elf[17]!=0||elf[18]!=40||elf[19]!=0)rc=96;
  }
  if(!rc)rc=action(s,c,"XCOMMIT",arg);
 }else if(!strcmp(verb,"UPLOAD_ENABLE"))rc=action(s,c,"XENABLE","");
 else if(!strcmp(verb,"REARM"))rc=action(s,c,"XREARM","");
 else if(!strcmp(verb,"ROLLBACK"))rc=action(s,c,"XROLLBACK",arg);
 else {
  if(!strcmp(verb,"SCREEN")){rc=action(s,c,"XSCREEN","");if(rc)goto finish;}
  const char *path=frame_path(!strcmp(verb,"SCREEN")?"screen":arg);
  int f=open(path,O_RDONLY);if(f<0){rc=96;goto finish;}
  char b[4096],hash[65];Sha hs;sha_init(&hs);unsigned size=0;int n;
  while((n=read(f,b,sizeof b))>0){size+=(unsigned)n;if(size>614400)break;sha_update(&hs,(unsigned char*)b,n);}
  if(n<0||size!=614400||lseek(f,0,0)!=0){close(f);rc=96;goto finish;}
  sha_final(&hs,hash);
  n=snprintf(b,sizeof b,"DATA %u %s %u %s\n",seq,verb,size,hash);
  if(sendall(c,b,n)){close(f);rc=98;goto finish;}
  u32 begin=millis();unsigned sent=0;
  while((n=read(f,b,sizeof b))>0){if(millis()-begin>=45000||sendall(c,b,n)){rc=98;break;}sent+=(unsigned)n;}
  close(f);if(n<0||sent!=size)rc=98;
 }
finish:
 unlink(RAM "/incoming");
 {int unlock=action(s,c,"XUNLOCK","");if(!rc)rc=unlock;}
 transfer_result(c,seq,verb,rc);
}

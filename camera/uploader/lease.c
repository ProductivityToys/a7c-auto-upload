/* ILCE-7C 2.00 only. Bounded RAM-only power-lease diagnostic.
 * Uses independently allocated ID; never alters another owner's request.
 * See rea-upm-mss-handlers.json and rea-power-id-helper.json.
 * Guardian retains ID allocation until final clear, preventing ID-reuse races.
 * Does not promise recovery from kernel deadlock or guardian failure.
 */
typedef unsigned int u32;
#ifndef LEASE_DIR
#define LEASE_DIR "/setting/a7c-uploader/ram"
#endif
extern int printf(const char *, ...), fflush(void *), strcmp(const char *,const char *);
extern int pipe(int *), fork(void), close(int), read(int,void *,unsigned), write(int,const void *,unsigned);
extern int poll(void *,unsigned long,int), kill(int,int), getpid(void), getppid(void), waitpid(int,int *,int);
extern unsigned sleep(unsigned);
extern int access(const char *,int),atoi(const char*);
extern void _exit(int);
extern int osal_dynamic_id(u32,u32,void *), osal_valloc_msg_wait(u32,void *,u32,int);
extern int osal_snd_sync_msg(u32,void *), osal_free_msg(u32,void *);
struct pollfd {int fd; short events,revents;};
static int message(u32 cmd,u32 id) {
 u32 *m=0; int rc=osal_valloc_msg_wait(0x924220,&m,16,1);
 if(rc || !m){printf("ALLOC rc=%d\n",rc);fflush(0);return rc?rc:-1;}
 m[-1]=id;m[0]=cmd;m[1]=id;m[2]=0;m[3]=0;
 rc=osal_snd_sync_msg(0x924220,m);
 printf("MSG cmd=%08x id=%08x transport=%d response=%08x\n",cmd,id,rc,m[1]);fflush(0);
 int fr=osal_free_msg(0x924220,m);return rc?rc:fr;
}
static int dump(void){
#ifdef LEASE_NO_DUMP
 return 0;
#else
 return message(0x92011c,0x920203);
#endif
}
int main(int argc,char **argv) {
 if(argc<2 || argc>3)return 64;
 int limit=argc==3?atoi(argv[2]):300;if(limit<2 || limit>86400)return 64;
 int owner=getppid();
 if(!strcmp(argv[1],"--dump"))return dump()!=0;
 int crash=!strcmp(argv[1],"--crash-test");
 int stall=!strcmp(argv[1],"--stall-test");
 int until=!strcmp(argv[1],"--upload-lease");
 int hold=until || !strcmp(argv[1],"--hold-test");
 if(!crash && !stall && !hold && strcmp(argv[1],"--lease-test"))return 64;
 u32 id=0;
 /* 0x37 matches native UpmWrapper caller's module category; allocation
  * is kernel-global (0x2a), not a hard-coded existing owner ID. */
 int rc=osal_dynamic_id(0x2a,0x37,&id);
 printf("GENERATE rc=%d id=%08x\n",rc,id);fflush(0);
 if(rc || !id)return 65;
 int p[2];if(pipe(p)) {osal_dynamic_id(0x4a,0,(void *)id);return 66;}
 int parent=getpid(),child=fork();
 if(child<0){close(p[0]);close(p[1]);osal_dynamic_id(0x4a,0,(void *)id);return 67;}
 if(!child){
  close(p[1]);struct pollfd f={p[0],1,0};
  int pr=poll(&f,1,until?(limit+10)*1000:hold?220000:8000);char done=0;
  if(pr>0)read(p[0],&done,1);
  /* Timeout: stop the setter before releasing; never reuse this ID early. */
  if(pr<=0 && getppid()==parent){kill(parent,9);sleep(1);}
  int cr=message(0x920202,id);
  int dr=dump();
  int rr=0;
  if(!cr)rr=osal_dynamic_id(0x4a,0,(void *)id);
  printf("GUARD clear=%d dump=%d release=%d completion=%d\n",cr,dr,rr,done);fflush(0);
  close(p[0]);_exit(cr||dr||rr?68:0);
 }
 close(p[0]);dump();
 rc=message(0x920203,id);dump();
 if(!rc){extern int open(const char*,int,...);int ready=open(LEASE_DIR "/lease.ready",64|1|512,0600);if(ready>=0){write(ready,"ready\n",6);close(ready);}}
 if(crash){printf("SIMULATED_OWNER_EXIT\n");fflush(0);_exit(73);}
 if(until) { for(int n=0;n<limit && getppid()==owner && access(LEASE_DIR "/lease.done",0);n++)sleep(1); }
 else sleep(hold?210:stall?30:2);
 int cr=message(0x920202,id);dump();
 write(p[1],"D",1);close(p[1]);
 int status=0;waitpid(child,&status,0);
 printf("PROBE_DONE set=%d clear=%d guardian_status=%d\n",rc,cr,status);fflush(0);
 return rc||cr||status?69:0;
}

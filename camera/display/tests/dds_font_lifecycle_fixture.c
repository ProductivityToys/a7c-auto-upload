/* Real fork/pipe/SIGKILL lifecycle against mock native RAM and messages.
 * Build with -I pointing to a private dds-text build's generated asset header.
 * No camera, proc access, native library execution or display device access.
 */
#define pread mock_pread
#define pwrite mock_pwrite
#define open mock_open
#define readlink mock_readlink
#define access mock_access
#define main probe_main
#ifdef TEST_DDS_EDGE
#include "../dds_edge_once.c"
#else
#include "../dds_text_once.c"
#endif
#undef main
#undef open
#include <assert.h>
#include <stdarg.h>
#include <sys/mman.h>
extern int open(const char *,int,...);
struct shared {
 struct native_state native;
 unsigned char font[FONT_BYTES];
 int redraws,installs,restores,guard_redraw,timer_armed,upload_active;
};
static struct shared *live;
static int writer_pid,scenario;
static int fake_upload_bind(struct dds_upload_request *r){
 memset(r,0,sizeof *r);r->owner=(u32)getpid();r->start=1;r->serial=1;r->limit=240;return 0;
}
static int fake_upload_active(const struct dds_upload_request *r){(void)r;return live->upload_active;}
static int fake_upload_context(void){return 1;}
static int readonly_only,readonly_captures;
#ifdef TEST_DDS_EDGE
static int position_budget=-1,position_read_failure;
#endif
static u32 allocation[4];
int mock_open(const char *path,int flags,...){
#ifdef DDS_PROGRESS_EXPERIMENT
 if(!strcmp(path,A7C_PROGRESS_RAM "display.progress"))return open("progress.fixture",O_RDONLY);
#endif
 if(readonly_only)assert(flags==O_RDONLY);
 assert(strstr(path,"/proc/")&&strstr(path,"/mem"));
 return open("/dev/null",O_RDWR);
}
ssize_t mock_readlink(const char *path,char *out,size_t n){
 (void)path;const char *s="/usr/bin/im.elf";assert(n>strlen(s));memcpy(out,s,strlen(s));return (ssize_t)strlen(s);
}
int mock_access(const char *path,int mode){assert(!strcmp(path,D "redraw")&&mode==1);return 0;}
ssize_t mock_pread(int fd,void *out,size_t n,off_t off){
 (void)fd;
 if(off==base&&n==4){u32 magic=0x464c457f;memcpy(out,&magic,4);return 4;}
 if(off==base+LIFE&&n==28){memcpy(out,live->native.life,n);return (ssize_t)n;}
 if(off==base+STATE&&n==208){
#ifdef TEST_DDS_EDGE
  if(position_read_failure)return -1;
#endif
  memcpy(out,live->native.slots,n);return (ssize_t)n;
 }
 if(off==base+FONT_ADDRESS&&n==FONT_BYTES){memcpy(out,live->font,n);return (ssize_t)n;}
 if(off==base+0x7db344U&&n==8){const unsigned char code[8]={3,0xeb,0xcb,3,0x13,0xf8,5,0xa0};memcpy(out,code,n);return (ssize_t)n;}
 assert(0);return -1;
}
ssize_t mock_pwrite(int fd,const void *p,size_t n,off_t off){
 assert(!readonly_only);
#ifdef TEST_DDS_EDGE
 if(off>=base+STATE+200&&off<base+STATE+204){
  unsigned offset=(unsigned)(off-base-STATE-200);assert(n<=4-offset);
  int restoring=!memcmp(p,original_position+offset,n);
  if(position_budget==0)return -1;
  if(position_budget>0&&(unsigned)position_budget<n)n=(unsigned)position_budget;
  if(position_budget>0)position_budget-=(int)n;
  if(getpid()==writer_pid&&scenario>=4&&scenario<12&&((scenario<8&&!restoring)||(scenario>=8&&restoring))){
   unsigned cut=(unsigned)(scenario-4)%4+1;assert(cut<=n);
   memcpy(live->native.slots+200+offset,p,cut);kill(getpid(),SIGKILL);_exit(99);
  }
  memcpy(live->native.slots+200+offset,p,n);return (ssize_t)n;
 }
#endif
 (void)fd;unsigned offset=(unsigned)(off-base-FONT_ADDRESS);
 assert(offset<FONT_BYTES&&n<=FONT_BYTES-offset);
 int restoring=!memcmp(p,original_font+offset,n);
 if(restoring)live->restores++;else live->installs++;
 if(getpid()==writer_pid&&((scenario==1&&!restoring)||(scenario==3&&restoring))){
  memcpy(live->font+offset,p,n>37?37:n);kill(getpid(),SIGKILL);_exit(99);
 }
 memcpy(live->font+offset,p,n);return (ssize_t)n;
}
int osal_valloc_msg_wait(u32 q,void *out,u32 size,int wait){
 assert(q==QUEUE&&size==12&&wait==0);*(u32**)out=allocation+1;return 0;
}
int osal_free_msg(u32 q,void *m){(void)q;(void)m;return 0;}
int osal_snd_msg(u32 q,void *m){
 assert(!readonly_only);
 assert(q==QUEUE);unsigned char *p=m;unsigned type=p[0]|((unsigned)p[1]<<8);
 live->native.life[4]=0;
 if(type==0x103){live->native.slots[18]=1;live->native.slots[20]=5;memcpy(live->native.slots+22,marker,8);}
 else if(type==0x104)live->native.slots[18]=0;
 else assert(type==0xff02);
 if(type==0xff02)live->native.slots[204]=live->native.slots[18];
 return 0;
}
int osal_snd_sync_direct(u32 q,void *payload){
 assert(!readonly_only);
 u32 *p=payload;assert(q==0x910040&&p[6]==239);
 if(p[4]==2){
  assert(shooting_overlay_mode&&p[0]==48&&p[8]==200000&&p[9]==0&&p[10]==2);
  assert(!live->native.slots[18]&&!live->native.slots[204]);live->timer_armed=1;
 }else {assert(p[4]==3);live->timer_armed=0;}
 p[5]=0;return 0;
}
static int fake_redraw(void){
#ifdef TEST_DDS_EDGE
 assert(!memcmp(live->native.slots+200,original_position,4));
#endif
 assert(!memcmp(live->font,original_font,FONT_BYTES));
 assert(!live->native.slots[18]&&!live->native.slots[204]&&!live->timer_armed);
 live->redraws++;if(getpid()!=writer_pid)live->guard_redraw=1;return 0;
}
static int fake_capture(const char *name){
 if(readonly_only){
  assert(!strcmp(name,"shooting.rle")&&allow_readonly_shooting_capture);
  readonly_captures++;return 0;
 }
#ifdef TEST_DDS_SHOOTING
 assert(shooting_overlay_mode&&allow_readonly_shooting_capture&&use_readonly_physical_capture);
 memset(pixels,0,sizeof pixels);
 if((scenario==12&&!strcmp(name,"dds-before.rle")) ||
    (scenario==13&&!strcmp(name,"dds-after.rle")))pixels[2*(SHOOTING_Y*640+SHOOTING_X)]=1;
#else
 assert(!allow_readonly_shooting_capture);
#endif
 if(!strcmp(name,"dds-during.rle")||!strcmp(name,"dds-late.rle")){
#ifdef TEST_DDS_SHOOTING
  assert(live->timer_armed);
#endif
#ifdef TEST_DDS_EDGE
  assert(!memcmp(live->native.slots+200,position_target(),4));
#endif
  assert(!memcmp(live->font,replacement_font,FONT_BYTES));
  if(scenario==2){kill(getpid(),SIGKILL);_exit(99);}
 }
 return 0;
}
int main(void){
#ifdef DDS_PROGRESS_EXPERIMENT
 int progress_file=open("progress.fixture",O_WRONLY|O_CREAT|O_TRUNC,0600);
 assert(progress_file>=0&&write(progress_file,"42\n",3)==3);close(progress_file);
#ifdef DDS_PROGRESS_BAR
 unsigned char allowed[8]={0x58,0x6b,0,0,0,0,0,0};
 unsigned char foreign[8]={0x1a,0x6b,0,0,0,0,0,0};assert(!progress_marker_owned(foreign));
 unsigned char full[8]={0x5a,0xaf,0,0,0,0,0,0};assert(!progress_marker_owned(full));
#else
 unsigned char allowed[8]={0x16,0x4c,0,0,0,0,0,0};
#endif
 assert(progress_marker_owned(allowed));allowed[7]=1;assert(!progress_marker_owned(allowed));
#endif
 live=mmap(0,sizeof *live,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANON,-1,0);assert(live!=MAP_FAILED);
 int cases=4;
#ifdef TEST_DDS_EDGE
 cases=12;
#endif
 for(scenario=0;scenario<cases;scenario++){
  memset(live,0,sizeof *live);base=0x6015000;
  live->native.life[0]=base+0x13b5238;live->native.life[2]=base+0x13b5288;
  live->native.life[3]=239;live->native.life[5]=1;
  u32 vt=base+0x13b5270;memcpy(live->native.slots,&vt,4);
  live->native.slots[200]=30;live->native.slots[202]=250;
  memcpy(live->font,original_font,FONT_BYTES);
  int child=fork();assert(child>=0);
  if(!child){
   writer_pid=getpid();redraw_action=fake_redraw;capture_action=fake_capture;
   char *args[]={"probe",
#ifdef TEST_DDS_SHOOTING
    "--once-shooting-idle",
#else
    "--once-idle",
#endif
    "162","6015000",0};
   _exit(probe_main(4,args));
  }
  int status=0;assert(waitpid(child,&status,0)==child);
  if(!scenario)assert(status==0);else assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGKILL);
  for(unsigned i=0;i<150&&!live->redraws;i++)usleep(20000);
  assert(live->redraws==1&&!memcmp(live->font,original_font,FONT_BYTES));
#ifdef TEST_DDS_EDGE
  assert(!memcmp(live->native.slots+200,original_position,4));
#endif
  assert(!live->native.slots[18]&&!live->native.slots[204]);
  assert(live->guard_redraw==(scenario!=0));
  /* Guardian observes state for another 1.5 seconds after reconstruction. */
  if(scenario)usleep(1700000);
 }
#ifdef TEST_DDS_EDGE
 timer_id=239;
 for(int install_cut=0;install_cut<=4;install_cut++){
  for(int restore_cut=0;restore_cut<=4;restore_cut++){
   memcpy(live->native.slots+200,original_position,4);
   position_budget=install_cut;int ir=position_change(0);
   assert((ir==0)==(install_cut==4));
   position_budget=restore_cut;(void)position_change(1);
   position_budget=-1;assert(position_change(1)==0&&position_check()==0);
  }
 }
 live->native.slots[201]=7;assert(position_change(1)==95);
 assert(live->native.slots[201]==7&&position_change(0)==95);
 memcpy(live->native.slots+200,original_position,4);
 position_read_failure=1;assert(position_change(0)==95&&position_change(1)==95);
 position_read_failure=0;position_budget=0;assert(position_change(1)==0);
 puts("PASS: edge position 25 short-write recovery pairs, foreign-byte/read refusal, idempotence; 12 real-fork lifecycle cases");
#endif
#ifdef TEST_DDS_SHOOTING
 position_budget=-1;capture_action=fake_capture;redraw_action=fake_redraw;writer_pid=getpid();
 char *shooting_args[]={"probe","--once-shooting-idle","162","6015000",0};
 int prior_redraws=live->redraws;
 scenario=12;assert(probe_main(4,shooting_args)==88);
 assert(live->redraws==prior_redraws && !live->native.slots[18]);
 assert(!memcmp(live->font,original_font,FONT_BYTES));
 scenario=13;assert(probe_main(4,shooting_args)==91);
 assert(live->redraws==prior_redraws+1&&!live->native.slots[18]);
 assert(!memcmp(live->font,original_font,FONT_BYTES));
 assert(!memcmp(live->native.slots+200,original_position,4));
 puts("PASS: occupied shooting baseline aborts before writes; changed post-cleanup region is reported as failure");
 /* A single setter must stay visible beyond the old two-second cycle. Normal
  * request removal and parent death/hang must still recover the native state. */
 for(unsigned fault=0;fault<3;fault++){
#ifdef DDS_PROGRESS_EXPERIMENT
  progress_file=open("progress.fixture",O_WRONLY|O_CREAT|O_TRUNC,0600);
  assert(progress_file>=0&&write(progress_file,"0\n",2)==2);close(progress_file);
#endif
  memset(live,0,sizeof *live);base=0x6015000;scenario=0;
  live->native.life[0]=base+0x13b5238;live->native.life[2]=base+0x13b5288;
  live->native.life[3]=239;live->native.life[5]=1;
  u32 vt=base+0x13b5270;memcpy(live->native.slots,&vt,4);
  memcpy(live->native.slots+200,original_position,4);memcpy(live->font,original_font,FONT_BYTES);
  live->upload_active=1;
  int setter=fork();assert(setter>=0);
  if(!setter){
   writer_pid=getpid();redraw_action=fake_redraw;capture_action=fake_capture;
   upload_bind_action=fake_upload_bind;upload_active_action=fake_upload_active;
   upload_context_action=fake_upload_context;
   char *args[]={"probe","--upload-shooting-idle","162","6015000",0};
   _exit(probe_main(4,args));
  }
  for(unsigned i=0;i<100&&!live->native.slots[204];i++)usleep(20000);
#ifdef DDS_PROGRESS_EXPERIMENT
  progress_file=open("progress.fixture",O_WRONLY|O_TRUNC);
  assert(progress_file>=0&&write(progress_file,"42\n",3)==3);close(progress_file);
#endif
  for(unsigned i=0;i<16;i++){
   usleep(200000);assert(live->native.slots[18]&&live->native.slots[204]);
   assert(!live->redraws&&!memcmp(live->font,replacement_font,FONT_BYTES));
  }
#ifdef DDS_PROGRESS_EXPERIMENT
  /* Guardian was forked with 0%; parent now displays 42%. Both must
   * recognize the fixed payload family and restore the unchanged font. */
#ifdef DDS_PROGRESS_BAR
  assert(live->native.slots[22]==0x58&&live->native.slots[23]==0x6b);
#else
  assert(live->native.slots[22]==0x16&&live->native.slots[23]==0x4c);
#endif
#endif
  if(fault==1)kill(setter,SIGKILL);
  else if(fault==2)kill(setter,SIGSTOP);
  else live->upload_active=0;
  int status=0;assert(waitpid(setter,&status,0)==setter);
  if(!fault)assert(status==0);else assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGKILL);
  for(unsigned i=0;i<150&&!live->redraws;i++)usleep(20000);
  assert(live->redraws==1&&!memcmp(live->font,original_font,FONT_BYTES));
  assert(!memcmp(live->native.slots+200,original_position,4));
  assert(!live->native.slots[18]&&!live->native.slots[204]);
  if(fault)usleep(1700000);
 }
 puts("PASS: continuous upload stays visible without interim cleanup; request completion, SIGKILL and lost heartbeat recover");
#endif
 struct shared unchanged=*live;
 readonly_only=1;capture_action=fake_capture;
 char *capture_args[]={"probe","--capture-shooting","162","6015000",0};
 assert(probe_main(4,capture_args)==0 && readonly_captures==1);
 assert(!memcmp(live,&unchanged,sizeof unchanged));
 char *physical_args[]={"probe","--capture-physical","162","6015000",0};
 assert(probe_main(4,physical_args)==0 && readonly_captures==2 && use_readonly_physical_capture);
 assert(!memcmp(live,&unchanged,sizeof unchanged));
 char *inspect_args[]={"probe","--inspect","162","6015000",0};
 assert(probe_main(4,inspect_args)==0 && !allow_readonly_shooting_capture && !use_readonly_physical_capture);
 assert(!memcmp(live,&unchanged,sizeof unchanged));
 munmap(live,sizeof *live);
 puts("PASS: shooting capture uses read-only process memory; no writes/messages/redraw; permission resets for inspect");
 puts("PASS: normal completion and SIGKILL during font install, display, font restore; real guardian recovered");
 return 0;
}

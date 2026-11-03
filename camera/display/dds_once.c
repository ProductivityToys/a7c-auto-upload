/* ILCE-7C 2.00 research only. One numeric DDS overlay, no direct memory writes
 * in the default build. DDS_TEXT_EXPERIMENT adds guarded shared-font writes.
 * Requires installer verification of libObj, libosal_uipc and utimer hashes.
 * RAM-only, no autostart, no power lease. Native asynchronous work is NOT
 * cancelled by killing this client: an independent child owns cleanup.
 * The native first-message flag remains initialized (0); we cancel scheduling,
 * not the native thread/allocation. A normal native resume reinitializes it.
 * Display modes require the separately verified redraw helper in the same
 * private RAM directory. Cleanup requests native reconstruction of the OSD.
 */
#include "../uploader/compat.h"
#include "capture_mapping.h"
#ifdef __arm__
extern int printf(const char *, ...), fflush(void *), sscanf(const char *,const char *,...);
extern int pread(int,void *,unsigned,long),readlink(const char *,char *,unsigned);
extern void *memset(void *,int,unsigned),*memcpy(void *,const void *,unsigned);
extern int memcmp(const void *,const void *,unsigned);
extern char *strstr(const char *,const char *);
#endif
#include "capture_physical.h"
#include "upload_lifetime.h"
extern int osal_valloc_msg_wait(u32,void *,u32,int),osal_snd_msg(u32,void *);
extern int osal_free_msg(u32,void *),osal_snd_sync_direct(u32,void *);
#define QUEUE 0x005c011dU
#define D "/setting/a7c-debug/ram/dds-once/"
#define LIFE 0x145aac8U
#define STATE 0x145aae4U
#define SHOOTING_X 562U
#define SHOOTING_Y 432U
static int memory_fd=-1, native_pid;
static u32 base,timer_id;
static unsigned shooting_overlay_mode;
static volatile int upload_stop;
static void upload_stop_signal(int sig){(void)sig;upload_stop=1;}
static int (*upload_bind_action)(struct dds_upload_request *)=dds_upload_bind;
static int (*upload_active_action)(const struct dds_upload_request *)=dds_upload_active;
static int quiet_upload_refresh;
#ifdef DDS_TEXT_EXPERIMENT
#include "dds_text_asset.h"
#ifdef DDS_PROGRESS_EXPERIMENT
#include "../uploader/upload_progress.h"
#ifdef DDS_PROGRESS_BAR
static unsigned char progress_marker[8]={0x16,0x6b,0,0,0,0,0,0};
#else
static unsigned char progress_marker[8]={0x10,0x2c,0,0,0,0,0,0};
#endif
#define marker progress_marker
static int progress_marker_owned(const unsigned char *m){
#ifdef DDS_PROGRESS_BAR
 unsigned steps=0,partial=0;
 for(unsigned i=0;i<4;i++){
  unsigned tile=(m[i/2]>>(i%2?0:4))&15;
  unsigned start=i==0?1:i==3?11:6;
  if(tile<start||tile>start+4||(partial&&tile!=start))return 0;
  steps+=tile-start;if(tile<start+4)partial=1;
 }
 if(steps>15)return 0;
#else
 if((m[0]>>4)!=1||((m[0]&15)!=0&&((m[0]&15)<2||(m[0]&15)>11))||
    (m[1]&15)!=12||(m[1]>>4)<2||(m[1]>>4)>11)return 0;
 #endif
 for(unsigned i=2;i<8;i++)if(m[i])return 0;
 return 1;
}
static int progress_update(const struct dds_upload_request *request){
 unsigned percent;
 if(progress_for_token(request->token,request->bytes,&percent))return 0;
#ifdef DDS_PROGRESS_BAR
 unsigned steps=percent*16/100;unsigned char tiles[4];
 for(unsigned i=0;i<4;i++){
  unsigned fill=steps>4?4:steps;
  tiles[i]=(unsigned char)(fill+(i==0?1:i==3?11:6));steps-=fill;
 }
 unsigned char a=(unsigned char)((tiles[0]<<4)|tiles[1]);
 unsigned char b=(unsigned char)((tiles[2]<<4)|tiles[3]);
#else
 unsigned char a=(unsigned char)(0x10|(percent<10?0:2+percent/10));
 unsigned char b=(unsigned char)(((2+percent%10)<<4)|12);
 #endif
 if(marker[0]==a&&marker[1]==b)return 0;
 marker[0]=a;marker[1]=b;
 printf("DDS_PROGRESS percent=%u\n",percent);fflush(0);return 1;
}
#else
#define marker text_marker
#endif
#else
static const unsigned char marker[8]={0xa7,0xc0,0,1,0,0,0,0};
#endif
struct native_state { u32 life[7]; unsigned char slots[208]; };
static u32 word(const void *p){u32 n;memcpy(&n,p,4);return n;}
static unsigned half(const unsigned char *p){return p[0]|((unsigned)p[1]<<8);}
static int at(u32 addr,void *p,unsigned size){
 return addr<0x80000000U && size && addr+size>addr &&
        pread(memory_fd,p,size,(long)addr)==(int)size?0:-1;
}
static int snapshot(struct native_state *s){
 u32 magic;
 if(at(base,&magic,4)||magic!=0x464c457fU||at(base+LIFE,s->life,28)||
    at(base+STATE,s->slots,208))return -1;
 if(s->life[0]!=base+0x13b5238U||s->life[2]!=base+0x13b5288U||
    word(s->slots)!=base+0x13b5270U||s->life[5]!=1||
    !s->life[3]||s->life[3]>=512||s->life[4]>1)return -1;
 return 0;
}
static int other_slots_idle(const struct native_state *s){
 for(unsigned i=0;i<8;i++){
  const unsigned char *p=s->slots+i*24;
  if(p[8]||word(p+12)||(i&&p[18]))return 0;
 }
 return 1;
}
static int ours_or_empty(const struct native_state *s){
 return !s->slots[18] || (s->slots[18]==1 && s->slots[20]==5 &&
#ifdef DDS_PROGRESS_EXPERIMENT
                         progress_marker_owned(s->slots+22));
#else
                         !memcmp(s->slots+22,marker,8));
#endif
}
static void state_log(const char *tag,const struct native_state *s){
 printf("DDS_STATE %s timer=%u first=%u override=%u visible=%u others_idle=%d\n",
  tag,s->life[3],s->life[4],s->slots[18],s->slots[204],other_slots_idle(s));fflush(0);
}
#ifdef DDS_TEXT_EXPERIMENT
#include "dds_font_adapter.h"

#else
static int experiment_prepare(void){return 0;}
static int experiment_install(void){return 0;}
static int experiment_restore(void){return 0;}
#endif
static int message(unsigned type){
 if(type!=0x103 && type!=0x104 && type!=0xff02)return 64;
 u32 *m=0;int r=osal_valloc_msg_wait(QUEUE,&m,12,0);
 if(r||!m)return 65;
 memset(m,0,12);m[-1]=QUEUE;m[0]=type;
 if(type==0x103){((unsigned char*)m)[3]=5;memcpy(m+1,marker,8);}
 r=osal_snd_msg(QUEUE,m);
 /* Successful asynchronous delivery transfers ownership to native receiver. */
 if(r){int f=osal_free_msg(QUEUE,m);printf("DDS_FREE rc=%d\n",f);}
 if(!quiet_upload_refresh || r){printf("DDS_SEND type=%04x rc=%d\n",type,r);fflush(0);}return r;
}
static int refresh_upload(void){
 #define UPLOAD_REFRESH_MS 50U
 quiet_upload_refresh=1;
 /* The request stays registered for this whole task. Refresh only;
  * repeating SET also queues a native refresh and duplicates every redraw. */
 int r=message(0xff02);
 quiet_upload_refresh=0;return r;
}
static int cancel_timer(void){
 struct native_state s;
 if(snapshot(&s)||s.life[3]!=timer_id||!other_slots_idle(&s)||!ours_or_empty(&s))return 70;
 u32 m[12]={48,0,0,0,3,0,0,0,0,0,0,0};m[6]=timer_id;
 int r=osal_snd_sync_direct(0x00910040,m);
 printf("DDS_CANCEL timer=%u transport=%d response=%d\n",timer_id,r,(int)m[5]);fflush(0);
 return r?r:(int)m[5];
}
static int arm_shooting_timer(void){
 /* Match libObj 0x7dbf74..0x7dbf7e -> 0x7dbc50: op=2, timer,
  * interval=200000 (u64), mode=2. The original first message already does
  * this for first=1. A verified cancelled same-session timer needs rearming
  * for first=0 so live-view repaint does not erase a single refresh forever.
  * This tests that hypothesis; flags still do not prove visible pixels. */
 struct native_state s;
 if(snapshot(&s)||s.life[3]!=timer_id||!other_slots_idle(&s)||s.slots[18]||s.slots[204])return 70;
 if(s.life[4])return 0;
 u32 m[12]={48,0,0,0,2,0,0,0,200000,0,2,0};m[6]=timer_id;
 int r=osal_snd_sync_direct(0x00910040,m);
 printf("DDS_ARM timer=%u interval=200000 mode=2 transport=%d response=%d\n",timer_id,r,(int)m[5]);fflush(0);
 return r?r:(int)m[5];
}
static int wait_state(int enabled,int visible){
 for(unsigned i=0;i<100;i++){
  struct native_state s;
  if(snapshot(&s)||s.life[3]!=timer_id||!other_slots_idle(&s)||!ours_or_empty(&s))return 71;
  if(s.life[4]==0 && s.slots[18]==enabled && (visible<0||s.slots[204]==visible))return 0;
  usleep(20000);
 }
 return 72;
}
static int native_redraw(void){
 int child=fork();if(child<0)return 78;
 if(!child){
  char pid[16],addr[16];snprintf(pid,sizeof pid,"%d",native_pid);snprintf(addr,sizeof addr,"%x",base);
  char *const args[]={D "redraw","--request",pid,addr,0};
  close(memory_fd);execv(args[0],args);_exit(127);
 }
 u32 start=millis();int status=0;
 while(millis()-start<8000){
  int r=waitpid(child,&status,1);
  if(r==child){printf("DDS_REDRAW status=%d\n",status);fflush(0);return status?78:0;}
  if(r<0)return 78;
  usleep(20000);
 }
 kill(child,9);waitpid(child,&status,0);return 78;
}
static int (*redraw_action)(void)=native_redraw;
static int clear_display(void){
 struct native_state s;
 if(snapshot(&s)||s.life[3]!=timer_id||!other_slots_idle(&s)||!ours_or_empty(&s))return 73;
 state_log("cleanup-before",&s);
 /* Queue a clear AFTER any delayed setter before deciding we are idle. An
  * untouched-looking state alone cannot prove an async setter was not queued.
  * Wait for first-message initialization before cancelling its timer. */
 if(message(0x104)||message(0xff02)||wait_state(0,0))return 75;
 /* Stop periodic scheduling before queueing the final redraw. In-flight
  * callbacks cannot rearm a cancelled timer: utimer mode 3 requires interval.
  * No timer-free, thread-exit or raw flag manipulation is performed. */
 if(cancel_timer())return 74;
 if(message(0xff02)||wait_state(0,0))return 75;
 return 0;
}
static int cleanup(void){
 /* Font recovery is attempted even if DDS conflict/queue checks refuse the
  * normal cleanup. A refusal must not silently strand our global font. */
 int cr=clear_display();int fr=experiment_restore();
 if(fr)return fr;
 if(cr)return cr;
 if(redraw_action())return 78;
 /* Observe several former timer periods, rather than accepting the first
  * cleared flag while an older callback could still be in flight. */
 for(unsigned i=0;i<15;i++){
  struct native_state s;
  usleep(100000);
  if(snapshot(&s)||s.life[3]!=timer_id||!other_slots_idle(&s)||
     s.slots[18]||s.slots[204])return 76;
 }
 struct native_state s;
 if(snapshot(&s))return 76;
 state_log("cleanup-after",&s);return 0;
}
static int dump_file(const char *name,const void *buf,unsigned n){
 char path[160];snprintf(path,sizeof path,D "%s",name);
 int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0)return -1;
 unsigned off=0;while(off<n){int r=write(fd,(const char*)buf+off,n-off);if(r<=0){close(fd);return -1;}off+=(unsigned)r;}
 return close(fd);
}
static char maps[262144];static unsigned char pixels[614400];
static unsigned allow_readonly_shooting_capture;
static unsigned use_readonly_physical_capture;
static unsigned char packed[98304];
static u32 upload_bitmap,upload_pixels,upload_physical;
static int upload_context_same(void){
 u32 manager[64],obj[32],desc[16];
 return upload_bitmap && !at(base+0x1453df0U,manager,sizeof manager) && manager[0x58/4]==1 &&
  manager[0x8c/4]==upload_bitmap && !at(upload_bitmap,obj,sizeof obj) &&
  obj[0]==base+0x13b1f50U && obj[2]==upload_pixels && obj[1] &&
  !at(obj[1],desc,sizeof desc) && desc[9]==upload_physical && desc[7]==1 &&
  half((const unsigned char*)desc+16)==640 && half((const unsigned char*)desc+18)==480;
}
static int (*upload_context_action)(void)=upload_context_same;
static unsigned pack_pixels(void){
 memcpy(packed,"A7R1",4);u32 bytes=sizeof pixels;memcpy(packed+4,&bytes,4);
 unsigned used=8;
 for(unsigned i=0;i<sizeof pixels/2;){
  unsigned value=half(pixels+2*i),count=1;
  while(i+count<sizeof pixels/2 && count<65535 && half(pixels+2*(i+count))==value)count++;
  if(used+4>sizeof packed)return 0;
  packed[used++]=(unsigned char)count;packed[used++]=(unsigned char)(count>>8);
  packed[used++]=(unsigned char)value;packed[used++]=(unsigned char)(value>>8);i+=count;
 }
 return used;
}
static int (*dump_action)(const char *,const void *,unsigned)=dump_file;
static int save_frame(const char *name){
 /* Fixed-size private RAM output for explicit physical reads: one standalone
  * screenshot, or named snapshots around a shooting display experiment.
  * Legacy display modes retain their 96 KiB RLE limit and abort behaviour. */
 if(use_readonly_physical_capture){
  const char *raw=0;
  if(shooting_overlay_mode){
   if(!strcmp(name,"dds-before.rle"))raw="dds-before.raw";
   if(!strcmp(name,"dds-during.rle"))raw="dds-during.raw";
   if(!strcmp(name,"dds-late.rle"))raw="dds-late.raw";
   if(!strcmp(name,"dds-after.rle"))raw="dds-after.raw";
  }else if(!strcmp(name,"shooting.rle"))raw="shooting.raw";
  if(!raw)return 89;
  printf("DDS_RAW name=%s bytes=%u\n",raw,(unsigned)sizeof pixels);fflush(0);
  return dump_action(raw,pixels,sizeof pixels)?87:0;
 }
 unsigned n=pack_pixels();if(!n)return 89;
 printf("DDS_PACK name=%s bytes=%u\n",name,n);fflush(0);
 return dump_action(name,packed,n)?87:0;
}
static int capture_frame(const char *name){
 /* Evidence only: no promise of an atomic frame or of the currently scanned
  * LCD. Validate the existing mapping; /dev/mem stays read-only and is allowed
  * only for explicit shooting capture/display modes, never legacy --once. */
 u32 manager[64],obj[32],desc[16],again[64];char path[64];
 if(at(base+0x1453df0U,manager,sizeof manager)||manager[0x58/4]!=1)return 80;
 u32 bitmap=manager[0x8c/4];
 if(!bitmap||at(bitmap,obj,sizeof obj)||obj[0]!=base+0x13b1f50U||
    !obj[1]||at(obj[1],desc,sizeof desc))return 81;
 const unsigned char *b=(const unsigned char*)desc;
 if(half(b+16)!=640||half(b+18)!=480||half(b+24)!=640||half(b+26)!=480||desc[7]!=1)return 82;
 snprintf(path,sizeof path,"/proc/%d/maps",native_pid);
 int fd=open(path,O_RDONLY);if(fd<0)return 83;
 unsigned used=0;int r;
 while(used<sizeof maps-1 && (r=read(fd,maps+used,sizeof maps-1-used))>0)used+=(unsigned)r;
 close(fd);if(used==sizeof maps-1)return 83;maps[used]=0;
 int found=0,physical_found=0;unsigned related=0;char *line=maps;
 for(unsigned i=0;i<used;i++)if(maps[i]=='\n'){
  maps[i]=0;unsigned lo,hi,offset;char flags[8],device[96];
  if(sscanf(line,"%x-%x %7s %x %*s %*s %95s",&lo,&hi,flags,&offset,device)==5){
   int stream=!strcmp(device,"/dev/stream");
   int shooting=allow_readonly_shooting_capture && !strcmp(device,"/dev/mem") &&
     capture_shooting_mapping_matches(lo,hi,offset,obj[2],sizeof pixels,desc[9]);
   if(!strcmp(flags,"rw-s") && (stream||shooting) &&
      capture_mapping_matches(lo,hi,offset,obj[2],sizeof pixels,desc[9]))found++;
   if(!strcmp(flags,"rw-s") && shooting)physical_found++;
   if(related<16 && ((obj[2]>=lo&&obj[2]<hi)||offset==desc[9])){
    printf("DDS_CAPTURE_MAP lo=%08x hi=%08x offset=%08x flags=%s device=%s readonly_shooting=%d\n",
           lo,hi,offset,flags,device,shooting);related++;
   }
  }
  line=maps+i+1;
 }
 if(found!=1){
  printf("DDS_CAPTURE_REJECT mapping_matches=%d bitmap=%08x pixels=%08x offset=%08x bytes=%u\n",
         found,bitmap,obj[2],desc[9],(unsigned)sizeof pixels);fflush(0);return 84;
 }
 if(use_readonly_physical_capture){
  if(physical_found!=1){
   printf("DDS_CAPTURE_REJECT physical_required matches=%d pixel_read_started=0\n",physical_found);
   fflush(0);return 84;
  }
  if(capture_physical_read(desc[9],sizeof pixels,pixels))return 84;
 }else{
  if(obj[2]>=0x80000000U||sizeof pixels>0x80000000U-obj[2])return 84;
  errno=0;int got=pread(memory_fd,pixels,sizeof pixels,(long)obj[2]);int e=errno;
  if(got!=(int)sizeof pixels){
   printf("DDS_CAPTURE_REJECT read_failed pixels=%08x bytes=%u got=%d errno=%d\n",
          obj[2],(unsigned)sizeof pixels,got,e);
   fflush(0);return 84;
  }
 }
 if(at(base+0x1453df0U,again,sizeof again))return 85;
 printf("DDS_CAPTURE name=%s front_unchanged=%d bitmap=%08x\n",name,again[0x8c/4]==bitmap,bitmap);fflush(0);
 if(again[0x8c/4]!=bitmap)return 86;
 if(shooting_overlay_mode&&!strcmp(name,"dds-before.rle")){
  upload_bitmap=bitmap;upload_pixels=obj[2];upload_physical=desc[9];
 }
 return save_frame(name);
}
static int capture(const char *name){
 int r=86;
 for(unsigned i=0;i<8 && r==86;i++){
  r=capture_frame(name);
  if(r==86)usleep(20000);
 }
 return r;
}
static int (*capture_action)(const char *)=capture;
static int shooting_region_empty(const char *phase){
 unsigned nonzero=0;
 /* Right/bottom viewport clipping: visible part of the unchanged 576x192
  * native destination. Never move this rectangle into the screen interior. */
 for(unsigned y=SHOOTING_Y;y<480;y++)for(unsigned x=SHOOTING_X;x<640;x++)
  if(half(pixels+2*(y*640+x)))nonzero++;
 printf("DDS_REGION phase=%s x=%u y=%u width=%u height=%u nonzero=%u\n",
  phase,SHOOTING_X,SHOOTING_Y,640-SHOOTING_X,480-SHOOTING_Y,nonzero);fflush(0);
 return nonzero?98:0;
}
static int attach(int pid,u32 addr){
 char path[64],exe[96];
 if(pid<2||addr<0x01000000U||addr>0x30000000U||addr%4096)return 64;
 native_pid=pid;base=addr;
 snprintf(path,sizeof path,"/proc/%d/exe",pid);
 int n=readlink(path,exe,sizeof exe-1);if(n<0)return 65;exe[n]=0;
 if(strcmp(exe,"/usr/bin/im.elf"))return 65;
 snprintf(path,sizeof path,"/proc/%d/mem",pid);memory_fd=open(path,O_RDONLY);
 struct native_state s;
 if(memory_fd<0||snapshot(&s))return 66;
 timer_id=s.life[3];state_log("attached",&s);return 0;
}
int main(int argc,char **argv){
 u32 started=millis();
 shooting_overlay_mode=0;upload_stop=0;upload_bitmap=0;quiet_upload_refresh=0;
#ifdef DDS_PROGRESS_EXPERIMENT
 memcpy(marker,text_marker,8);
#endif
 int continuous_upload=0;
 struct dds_upload_request upload_request;
 if(argc!=4)return 64;
#ifdef DDS_EDGE_EXPERIMENT
 continuous_upload=!strcmp(argv[1],"--upload-shooting")||!strcmp(argv[1],"--upload-shooting-idle");
 shooting_overlay_mode=continuous_upload||!strcmp(argv[1],"--once-shooting")||!strcmp(argv[1],"--once-shooting-idle");
#endif
 if(!shooting_overlay_mode && strcmp(argv[1],"--inspect")&&strcmp(argv[1],"--capture")&&strcmp(argv[1],"--capture-shooting")&&strcmp(argv[1],"--capture-physical")&&strcmp(argv[1],"--once")&&strcmp(argv[1],"--once-idle"))return 64;
 use_readonly_physical_capture=shooting_overlay_mode||!strcmp(argv[1],"--capture-physical");
 allow_readonly_shooting_capture=use_readonly_physical_capture||!strcmp(argv[1],"--capture-shooting");
 char *end=0;unsigned long long a=strtoull(argv[3],&end,16);
 if(!end||*end||a>0xffffffffULL)return 64;
 int r=attach(atoi(argv[2]),(u32)a);if(r)return r;
 struct native_state before;
 if(snapshot(&before))return 66;
 if(!strcmp(argv[1],"--inspect")){
#ifdef DDS_TEXT_EXPERIMENT
  printf("DDS_OBSERVED x=%u y=%u marker=%02x%02x\n",half(before.slots+200),half(before.slots+202),before.slots[22],before.slots[23]);fflush(0);
  unsigned char font[FONT_BYTES];
  if(at(base+FONT_ADDRESS,font,FONT_BYTES)||memcmp(font,original_font,FONT_BYTES))return 92;
  printf("DDS_FONT original_matches=1 bytes=128\n");fflush(0);
#ifdef DDS_EDGE_EXPERIMENT
  if(position_check())return 95;
  printf("DDS_POSITION original_matches=1 x=30 y=250\n");fflush(0);
#endif
#endif
  return 0;
 }
 if(!strcmp(argv[1],"--capture-shooting")){
  return capture_action("shooting.rle");
 }
 if(!strcmp(argv[1],"--capture-physical"))return capture_action("shooting.rle");
 if(!strcmp(argv[1],"--capture"))return capture_action("dds-before.rle");
 if(access(D "redraw",1 /* X_OK */))return 79;
 /* --once-idle is only for a host-verified same-session prior cancellation;
  * the zero lazy-init flag alone does not prove a timer is inactive. */
 unsigned expected_first=(!strcmp(argv[1],"--once")||!strcmp(argv[1],"--once-shooting")||!strcmp(argv[1],"--upload-shooting"))?1:0;
 if(before.life[4]!=expected_first||!other_slots_idle(&before)||before.slots[18]||before.slots[204]||
    half(before.slots+200)!=30||half(before.slots+202)!=250)return 67;
 if(continuous_upload && (upload_bind_action(&upload_request)||!upload_active_action(&upload_request)))return 64;
 r=experiment_prepare();if(r)return r;
 int p[2],ready[2];if(pipe(p)||pipe(ready))return 68;
 int parent=getpid(),consumer=getppid(),child=fork();if(child<0)return 69;
 if(!child){
  close(p[1]);close(ready[0]);char armed='R';
  if(write(ready[1],&armed,1)!=1)_exit(69);
  close(ready[1]);
  if(dds_guard_wait(p[0],continuous_upload,continuous_upload?upload_request.limit:0)){close(p[0]);_exit(0);}
  /* Stop the setter before any fallback cleanup, including EOF/crash. */
  if(getppid()==parent)kill(parent,9);
  usleep(100000);
  int cr=cleanup();printf("DDS_GUARD cleanup=%d\n",cr);fflush(0);
  close(p[0]);_exit(cr?90:0);
 }
 close(p[0]);close(ready[1]);signal(SIGPIPE,SIG_IGN);
 if(continuous_upload){signal(SIGTERM,upload_stop_signal);signal(SIGINT,upload_stop_signal);}
 struct pollfd rf={ready[0],1,0};char armed=0;
 int armed_ok=poll(&rf,1,2000)>0 && read(ready[0],&armed,1)==1 && armed=='R';
 close(ready[0]);
 if(!armed_ok){kill(child,9);waitpid(child,0,0);close(p[1]);return 69;}
 printf("DDS_GUARD ready=1\n");fflush(0);
 int cap_before=capture_action("dds-before.rle");
 if(!cap_before&&shooting_overlay_mode)cap_before=shooting_region_empty("before");
 /* Without a readable baseline, do not initiate native display work. */
 if(cap_before){
  char done='D';write(p[1],&done,1);close(p[1]);int status=0;waitpid(child,&status,0);
  printf("DDS_ABORT baseline_capture=%d guardian=%d\n",cap_before,status);fflush(0);return 88;
 }
 r=experiment_install();
 if(!r&&shooting_overlay_mode)r=arm_shooting_timer();
#ifdef DDS_PROGRESS_EXPERIMENT
 if(continuous_upload)(void)progress_update(&upload_request);
#endif
 if(!r)r=message(0x103);
 if(!r)r=message(0xff02);
 if(!r)r=wait_state(1,1);
 int cap_during=-1,cap_late=shooting_overlay_mode?-1:0;
 if(!r){
  if(shooting_overlay_mode){
   if(continuous_upload && write(p[1],"H",1)!=1)r=69;
   /* Native +0xcc is set BEFORE 0x7db5a8 renders. It is not a completion
    * fence. Sample later twice; neither elapsed time nor the flag proves
    * that the physical LCD scanned these pixels. No extra draw requests. */
   if(continuous_upload){
    unsigned refreshes=0;
#ifdef DDS_PROGRESS_EXPERIMENT
    u32 progress_at=millis();
#endif
    /* Full-frame readback blocks this setter long enough for live-view to
     * repaint over it. Keep sampling in a separate read-only diagnostic;
     * production uploads capture only the baseline and restored frame. */
    cap_during=0;cap_late=0;
    printf("DDS_UPLOAD continuous=1 watchdog_ms=3000 limit=%u\n",upload_request.limit);fflush(0);
    printf("DDS_UPLOAD_OWNER owner=%u start=%u serial=%u\n",upload_request.owner,upload_request.start,upload_request.serial);fflush(0);
    printf("DDS_UPLOAD_CAPTURE policy=before_after_only\n");fflush(0);
    while(!r&&!upload_stop&&getppid()==consumer&&
          millis()-started<upload_request.limit*1000U&&upload_active_action(&upload_request)){
     struct native_state live;
     if(!upload_context_action()){printf("DDS_UPLOAD_END context_changed=1\n");fflush(0);break;}
     if(snapshot(&live)||live.life[3]!=timer_id||!other_slots_idle(&live)||
        !ours_or_empty(&live)||live.slots[18]!=1){r=71;break;}
     if(write(p[1],"H",1)!=1){r=69;break;}
     int changed=0;
#ifdef DDS_PROGRESS_EXPERIMENT
     if(millis()-progress_at>=1000){progress_at=millis();changed=progress_update(&upload_request);}
#endif
     r=changed?message(0x103):refresh_upload();if(r)break;refreshes++;
     usleep(UPLOAD_REFRESH_MS*1000U);
    }
    printf("DDS_UPLOAD_REFRESH count=%u interval_ms=%u\n",refreshes,UPLOAD_REFRESH_MS);fflush(0);
   }else{
    usleep(500000);
    printf("DDS_SNAPSHOT phase=during elapsed_ms=%u\n",millis()-started);fflush(0);
    cap_during=capture_action("dds-during.rle");
    if(!cap_during)(void)shooting_region_empty("during");
    usleep(750000);
   }
   if(!continuous_upload){
    printf("DDS_SNAPSHOT phase=late elapsed_ms=%u\n",millis()-started);fflush(0);
    cap_late=capture_action("dds-late.rle");
    if(!cap_late)(void)shooting_region_empty("late");
    usleep(750000);
   }
  }else{cap_during=capture_action("dds-during.rle");sleep(2);}
 }
 if(continuous_upload)(void)write(p[1],"C",1);
 int cr=cleanup();
 int cap_after=cr?-1:capture_action("dds-after.rle");
 if(!cap_after&&shooting_overlay_mode)cap_after=shooting_region_empty("after");
 char done=cr?'F':'D';write(p[1],&done,1);close(p[1]);
 int status=0;waitpid(child,&status,0);
 printf("DDS_DONE display=%d cleanup=%d guardian=%d captures=%d,%d,%d\n",r,cr,status,cap_before,cap_during,cap_after);fflush(0);
 if(shooting_overlay_mode){printf("DDS_LATE capture=%d\n",cap_late);fflush(0);}
 printf("DDS_ELAPSED ms=%u\n",millis()-started);fflush(0);
 return r||cr||status||cap_during||cap_late||cap_after?91:0;
}

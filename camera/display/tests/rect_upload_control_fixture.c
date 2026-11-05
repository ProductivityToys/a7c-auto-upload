/* Real request/progress file parsers; native mailbox/frames/time simulated. */
#include "../../uploader/compat.h"
#include <assert.h>
#include <sys/stat.h>
#define DDS_PROC_ROOT "./proc/"
#define DDS_UPLOAD_RAM "./"
#define DDS_DISPLAY_RAM "./"
#define A7C_PROGRESS_RAM "./"
#include "../upload_lifetime.h"
#include "../../uploader/upload_progress.h"
#include "../module/event_state.h"
typedef unsigned U;
static struct dds_upload_request upload_request;
static U event_marker_address=4096,detail[8],tick,steps,scenario,commands[600],count,photos;
static int writer=10,guard_writer;
#ifdef RECT_SERVICE_TRIAL
static U redraws,mailbox,idle_test;
static int frame_redraw(int pid){assert(pid==162);redraws++;if(scenario==7||idle_test==3)return 90;detail[3]++;detail[5]=mailbox?(mailbox&127):100;return 0;}
#endif
static struct event_marker marker;
static int event_read(struct event_marker *m){*m=marker;return 0;}
static int rd(U address,void *out,U n){assert(address==4096+sizeof marker&&n==sizeof detail);memcpy(out,detail,n);return 0;}
static int frame_snapshot(int pid,const char *name,int empty){assert(pid==162&&!strcmp(name,"during")&&!empty);photos++;return 0;}
static void put(const char *name,const char *s){int f=open(name,O_CREAT|O_WRONLY|O_TRUNC,0600);assert(f>=0);assert(write(f,s,strlen(s))==(int)strlen(s));close(f);}
static void progress(unsigned value,int foreign){char row[160];snprintf(row,sizeof row,"%s%u\n",foreign?"999 2 3 240\n":upload_request.token,value);put("display.progress",row);}
static int publish(int fd,const void *p,unsigned n,long address){
 assert(fd==10&&n==4&&address==4096+sizeof marker+32);U word=*(const U *)p;assert(count<600);commands[count++]=word;
 if(scenario==3&&word)return 2;
#ifdef RECT_SERVICE_TRIAL
 if(!word){mailbox=0;if(idle_test==1)detail[5]=100;}
#endif
 if(word){
#ifdef RECT_SERVICE_TRIAL
  mailbox=word;if(scenario>=6)return 4;
#endif
  detail[3]++;detail[5]=word&127;marker.captured=1;marker.tid=403;}
 return 4;
}
static unsigned fake_millis(void){return tick;}
static int fake_poll(void *fds,unsigned long n,int delay){
#ifdef RECT_SERVICE_TRIAL
 if(idle_test){assert(!fds&&!n&&delay==50);tick+=50;return 0;}
#endif
 assert(!fds&&!n&&delay==500);tick+=500;steps++;
 if(steps==1){progress(42,scenario==1);if(scenario==2)put("display.active","999 2 3 240\n");if(scenario==4)detail[6]=3;}
 if(steps==2)progress(99,0);
 if((scenario!=5&&steps==3)||(scenario==5&&steps==130))unlink("display.active");
 return 0;
}
#define RECT_UPLOAD_REDRAW frame_redraw
#define pwrite publish
#define millis fake_millis
#define poll fake_poll
#include "../module/rect_upload_control.h"
#ifdef RECT_SERVICE_TRIAL
#include "../module/rect_service_control.h"
#endif
int main(void){
 char stat[1024],path[64];U start=1234;
 assert(!mkdir("proc",0700));snprintf(path,sizeof path,"proc/%u",(U)getpid());assert(!mkdir(path,0700));
 snprintf(path,sizeof path,"proc/%u/stat",(U)getpid());
 snprintf(stat,sizeof stat,"%u (test process) S",(U)getpid());
 for(unsigned i=4;i<22;i++)strcat(stat," 0");strcat(stat," 1234 0\n");put(path,stat);
 for(scenario=0;scenario<
#ifdef RECT_SERVICE_TRIAL
  8
#else
  6
#endif
  ;scenario++){
  memset(detail,0,sizeof detail);memset(&marker,0,sizeof marker);tick=steps=count=photos=0;
#ifdef RECT_SERVICE_TRIAL
  redraws=mailbox=0;detail[5]=100;
#endif
  snprintf(upload_request.token,sizeof upload_request.token,"%u %u 1 240\n",(U)getpid(),start);
  put("display.active",upload_request.token);assert(!dds_upload_bind(&upload_request));progress(10,0);
  int pipefd[2];assert(!pipe(pipefd));guard_writer=pipefd[1];
  int rc=rect_upload_wait(162);assert(rc==(scenario==3||scenario==4?-1:0));assert(count&&commands[count-1]==0);
  if(scenario==5){
#ifdef RECT_SERVICE_TRIAL
   assert(tick==65000&&count==131);
#else
   assert(tick==55000&&count==111);
#endif
  }
  if(scenario==0){assert(count==4&&photos==
#ifdef RECT_SERVICE_TRIAL
   0
#else
   1
#endif
   );assert((commands[0]&127)==10&&(commands[1]&127)==42&&(commands[2]&127)==99);}
  if(scenario==1)assert(count==4&&(commands[1]&127)==10);
  if(scenario==2||scenario==4)assert(count==2);
  if(scenario==3)assert(count==2&&photos==0);
#ifdef RECT_SERVICE_TRIAL
  if(scenario<6)assert(!redraws);
  else assert(redraws==2&&count==4); /* No last update after request ended. */
#endif
  close(pipefd[0]);close(pipefd[1]);unlink("display.active");unlink("display.progress");
 }
#ifdef RECT_SERVICE_TRIAL
 scenario=0;
 for(idle_test=1;idle_test<=5;idle_test++){
  tick=redraws=0;memset(detail,0,sizeof detail);detail[3]=1;detail[5]=42;
  if(idle_test==4)detail[6]=1;
  if(idle_test==5)detail[5]=102;
  assert(rect_service_return_idle(162)==(idle_test==3||idle_test==4?-1:0));
  assert(redraws==((idle_test==2||idle_test==3)?1:0));
  if(idle_test==2)assert(tick==550&&detail[5]==100);
 }
#endif
 puts("RECT_UPLOAD_CONTROL_OK real_token_parser progress identity_change partial_write module_stop");
}

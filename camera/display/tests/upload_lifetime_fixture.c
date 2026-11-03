#include "../../uploader/compat.h"
#define DDS_UPLOAD_RAM "./"
#define DDS_DISPLAY_RAM "./"
#define DDS_PROC_ROOT "proc/"
#define DDS_ACTIVE_WATCHDOG_MS 80U
#define DDS_CLEANUP_WATCHDOG_MS 250U
#include "../upload_lifetime.h"
#include <assert.h>
#include <sys/stat.h>
static void put(const char *path,const char *text){
 int f=open(path,O_WRONLY|O_CREAT|O_TRUNC,0600);assert(f>=0);
 assert(write(f,text,strlen(text))==(int)strlen(text));assert(!close(f));
}
static void token_tests(void){
 struct dds_upload_request r;
 const char *bad[]={"", "1 2 3 240", "2 0 3 240", "2 2 0 240", "2 2 3 239", "2 2 3 86001",
  "2 2 3 -240", "2 2 3 240 extra", "2 2 3 240\nextra", "4294967296 2 3 240", "2 2 3"};
 for(unsigned i=0;i<sizeof bad/sizeof *bad;i++){
  snprintf(r.token,sizeof r.token,"%s",bad[i]);assert(dds_upload_parse(&r));
 }
 char expected[128],path[96],stat[1024];unsigned pid=(unsigned)getpid();
 snprintf(expected,sizeof expected,"%u 1234 1 240\n",pid);put("display.active",expected);
 assert(!dds_upload_bind(&r));assert(r.owner==pid&&r.start==1234&&r.limit==240);
 assert(!mkdir("proc",0700));snprintf(path,sizeof path,"proc/%u",pid);assert(!mkdir(path,0700));
 snprintf(path,sizeof path,"proc/%u/stat",pid);
 snprintf(stat,sizeof stat,"%u (name with ) spaces) S",pid);
 for(unsigned i=4;i<22;i++)strcat(stat," 0");
 strcat(stat," 1234 0\n");put(path,stat);assert(dds_upload_active(&r));
 put("stop","1");assert(!dds_upload_active(&r));assert(!unlink("stop"));
 put("cancel","1");assert(!dds_upload_active(&r));assert(!unlink("cancel"));
 put("display.active","2 1234 2 240\n");assert(!dds_upload_active(&r));put("display.active",expected);
 put(path,"1 (reused pid) S 0\n");assert(!dds_upload_active(&r));
 char overflow[256];memset(overflow,'0',sizeof overflow);int f=open("display.active",O_WRONLY|O_TRUNC);
 assert(f>=0&&write(f,overflow,sizeof overflow)==sizeof overflow);close(f);assert(dds_upload_bind(&r));
 puts("PASS upload lifetime: strict bounds, request replacement, PID reuse, stop/cancel and bounded reads");
}
static int guard_case(unsigned scenario){
 int p[2];assert(!pipe(p));int child=fork();assert(child>=0);
 if(!child){close(p[1]);_exit(dds_guard_wait(p[0],scenario!=5,240)?0:3);}
 close(p[0]);
 if(scenario==0){for(unsigned i=0;i<5;i++){assert(write(p[1],"H",1)==1);usleep(30000);}assert(write(p[1],"D",1)==1);}
 if(scenario==1){assert(write(p[1],"H",1)==1);usleep(150000);}
 if(scenario==2){assert(write(p[1],"H",1)==1);assert(write(p[1],"C",1)==1);usleep(150000);assert(write(p[1],"D",1)==1);}
 if(scenario==3){assert(write(p[1],"C",1)==1);assert(write(p[1],"C",1)==1);}
 if(scenario==4){assert(write(p[1],"F",1)==1);}
 if(scenario==5){usleep(100000);assert(write(p[1],"D",1)==1);}
 close(p[1]);int status;assert(waitpid(child,&status,0)==child);assert(WIFEXITED(status));return WEXITSTATUS(status);
}
int main(void){
 signal(SIGPIPE,SIG_IGN);token_tests();
 assert(guard_case(0)==0);assert(guard_case(1)==3);assert(guard_case(2)==0);
 assert(guard_case(3)==3);assert(guard_case(4)==3);assert(guard_case(5)==0);
 assert(guard_case(6)==3);
 puts("PASS real-pipe guardian: renewal, stale heartbeat, bounded cleanup, repeat-C rejection, failure/EOF and manual mode");
 return 0;
}

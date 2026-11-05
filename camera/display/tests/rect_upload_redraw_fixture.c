/* rect_upload_redraw keeps the active guardian alive across a slow redraw
 * helper (real fork/exec/wait), and reports a lost guardian. */
#include "../../uploader/compat.h"
#include <assert.h>
typedef unsigned U;
static int guard_writer=-1;
static U frame_base=0x1000,mapping_calls;
#ifndef FRAME_REDRAW
#define FRAME_REDRAW "./slow-redraw"
#endif
static int frame_mapping(int pid,U *base,U pixels){(void)pixels;assert(pid==162);mapping_calls++;*base=frame_base;return 0;}
static struct {char token[64];unsigned long long bytes;U limit;} upload_request;
#define RECT_SERVICE_TRIAL
static int event_marker_address;
#include "../module/event_state.h"
static int event_read(struct event_marker *m){(void)m;return 0;}
static int rd(U a,void *o,U n){(void)a;(void)o;(void)n;return 0;}
static int dds_upload_active(const void *r){(void)r;return 0;}
static int progress_for_token(const char *t,unsigned long long b,unsigned *p){(void)t;(void)b;(void)p;return 1;}
static int writer=-1;
#include "../module/rect_upload_control.h"
int main(int argc,char **argv){
 int fds[2];assert(!pipe(fds));guard_writer=fds[1];
 int lost=argc>1&&!strcmp(argv[1],"lost");
 if(lost)close(fds[0]);
 signal(SIGPIPE,SIG_IGN);
 int rc=rect_upload_redraw(162);
 if(lost){assert(rc==91);printf("REDRAW_LOST_OK\n");return 0;}
 close(fds[1]);
 char b[64];int n=0,k;while((k=read(fds[0],b+n,sizeof b-n))>0)n+=k;
 int beats=0;for(int i=0;i<n;i++){assert(b[i]=='H');beats++;}
 printf("rc=%d beats=%d mapping=%u\n",rc,beats,mapping_calls);
 assert(rc==0&&mapping_calls==1&&beats>=5);
 printf("REDRAW_HEARTBEAT_OK\n");return 0;
}

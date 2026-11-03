/* One bounded ILCE-7C 2.00 marker trial. Never generic code execution.
 * Requires host hash/mount verification and immutable staged marker. */
#if defined(A7C_SERVICE_NO_IDLE) || defined(A7C_SERVICE_SINGLE_BUFFER) || defined(A7C_SERVICE_LIFECYCLE_ACK)
/* Multiple bounded trial phases share one 32 KiB trace. Keep validation and
 * summary counts; omit unrelated loaded-module rows from each inventory. */
#define IM_MODULES_SUMMARY
#endif
#define main inventory_main
#include "../im_modules.c"
#undef main
#include "path_transaction.h"
#include "module_contract.h"
#if TEXT_TRIAL
#include "text_state.h"
#if TEXT_TRIAL >= 3
#define COMPOSE_TRIAL
#endif
#if TEXT_TRIAL >= 2
#if TEXT_TRIAL == 5
#define SMALL_POOL_TRIAL
#endif
#include "managed_buffer.h"
#endif
#endif
extern int pwrite(int,const void *,unsigned,long),pipe(int *),fork(void);
extern int write(int,const void *,unsigned),waitpid(int,int *,int),kill(int,int);
extern int poll(void *,unsigned long,int),fflush(void *),usleep(unsigned);
extern void _exit(int);
extern void *memcpy(void *,const void *,unsigned);
extern int osal_snd_sync_direct(unsigned,void *);
#ifdef RECT_UPLOAD_TRIAL
#include "../../uploader/compat.h"
#include "../upload_lifetime.h"
#include "../../uploader/upload_progress.h"
static struct dds_upload_request upload_request;
#endif
#ifdef RECT_SERVICE_TRIAL
#include "rpc_guard.h"
static int rpc_completed;
#endif
#ifdef SCREEN_TRIAL
#include "frame_control.h"
#endif
struct poll_fd {int fd;short events,revents;};
static int writer=-1,guard_writer=-1;
static U pinned_base,path_address;
static struct path_transaction tx;
#ifdef EVENT_TRIAL
#include "event_control.h"
#endif
#if TEXT_TRIAL == 3
static int failed_blit_finished;
#endif
static int descriptor_valid(void) {
    U words[11];
    if(database_base!=pinned_base || rd(pinned_base+0x105d4,words,sizeof words))return -1;
    for(U i=0;i<11;i++)
        if(words[i]!=descriptor_words[i]+(i>=4 && descriptor_words[i]?pinned_base:0))return -1;
    return 0;
}
static int path_read_native(unsigned char *out) {
    return descriptor_valid()?-1:rd(path_address,out,PATH_BYTES);
}
static int path_write_native(unsigned off,const unsigned char *p,unsigned n) {
    if(descriptor_valid() || off>=PATH_BYTES || !n || n>PATH_BYTES-off)return -1;
    return pwrite(writer,p,n,(long)(path_address+off));
}
static int loaded(void) {
    U head,seen[256],count=0;
    if(rd(0x15514,&head,4))return -1;
    while(head) {
        if(count==256)return -1;
        for(U i=0;i<count;i++)if(seen[i]==head)return -1;
        seen[count++]=head;
        U node[8],entry[11];
        if(rd(head,node,sizeof node)||rd(node[2],entry,sizeof entry))return -1;
        if((entry[3]&65535)==2031)return 1;
        head=node[0];
    }
    return 0;
}
static int refresh(int pid) {
    region_count=database_base=0;
    return get_maps(pid)||database_base!=pinned_base?-1:0;
}
static int send_command(U op) {
    printf("MODULE_RPC_BEGIN op=%08x\n",op);fflush(0);
#ifdef RECT_SERVICE_TRIAL
    rpc_completed=0;
    if(guard_writer>=0 && write(guard_writer,"B",1)!=1)return -1;
#endif
    int fds[2];if(pipe(fds))return -1;
    fflush(0);int child=fork();
    if(child<0){close(fds[0]);close(fds[1]);return -1;}
    if(!child) {
        close(fds[0]);if(guard_writer>=0)close(guard_writer);
        alarm(5);
        U m[8]={32,0,0,0,op,2031,3,0xa7c00001};
        int result[2];result[0]=osal_snd_sync_direct(0x94016a,m);result[1]=(int)m[5];
        int sent=write(fds[1],result,sizeof result);close(fds[1]);
        _exit(sent==(int)sizeof result?0:1);
    }
    close(fds[1]);int status=0;
    int w=waitpid(child,&status,0);int result[2]={-1,-1};
    int n=read(fds[0],result,sizeof result);close(fds[0]);
    printf("MODULE_RPC op=%08x wait=%d status=%d bytes=%d transport=%d result=%d\n",
           op,w,status,n,result[0],result[1]);fflush(0);
#ifdef RECT_SERVICE_TRIAL
    rpc_completed=module_rpc_complete(w,child,status,n,result[0]);
    if(rpc_completed && guard_writer>=0 && write(guard_writer,"K",1)!=1)rpc_completed=0;
    return rpc_completed?result[1]:-1;
#else
    return w==child && status==0 && n==(int)sizeof result && !result[0]?result[1]:-1;
#endif
}
static int marker_state(int pid,const char *phase) {
    char path[64],data[262144];
    snprintf(path,sizeof path,"/proc/%d/maps",pid);int f=open(path,0);if(f<0)return -1;
    U used=0;int n;
    while(used<sizeof data-1 && (n=read(f,data+used,sizeof data-1-used))>0)used+=(U)n;
    close(f);if(used==sizeof data-1)return -1;data[used]=0;
    U base=0;char *line=data;
    while(*line) {
        char *end=line;while(*end && *end!='\n')end++;char next=*end;*end=0;
        U lo,hi,offset;char perm[5],name[128]={0};
        if(sscanf(line,"%x-%x %4s %x %*s %*s %127s",&lo,&hi,perm,&offset,name)==5 &&
           !offset && !strcmp(name,MODULE_PATH) && (!base || lo<base))base=lo;
        if(!next)break;line=end+1;
    }
    U s[8];if(!base || refresh(pid) || rd(base+MARKER_OFFSET,s,sizeof s))return -1;
    printf("MODULE_MARKER phase=%s base=%08x magic=%08x version=%u init=%u exit=%u sus=%u res=%u inact=%u act=%u\n",
           phase,base,s[0],s[1],s[2],s[3],s[4],s[5],s[6],s[7]);fflush(0);
    int valid=s[0]==0x41374d31 && s[1]==MODULE_VERSION && s[2]==1 && s[3]==(!strcmp(phase,"after_exit")?1U:0U);
#ifdef EVENT_TRIAL
    event_marker_address=base+MARKER_OFFSET;
    struct event_marker e;U current=0,view=0,internal=0;
    if(event_read(&e)||!e.slot||rd(e.slot,&current,4))return -1;
#ifdef PRESENT_TRIAL
    U obj=e.original-0x675085;
    if(e.slot!=obj+0x145abe4||e.view!=obj+0x1453918||e.internal!=obj+0x1453df0)return -1;
    (void)view;(void)internal;
    U pixels[6];if(rd(event_marker_address+sizeof e,pixels,sizeof pixels))return -1;
    printf("MODULE_PRESENT target=%08x pixels=%08x before=%u after=%u matched=%u original_completed=%u\n",
           pixels[0],pixels[1],pixels[2],pixels[3],pixels[4],pixels[5]);
#ifdef PRESENT_ALIAS_TRIAL
    U alias[4];if(rd(event_marker_address+sizeof e+sizeof pixels,alias,sizeof alias))return -1;
    printf("MODULE_ALIAS address=%08x before=%u after=%u matched=%u readonly=1\n",alias[0],alias[1],alias[2],alias[3]);
#ifdef PRESENT_SYNC_TRIAL
    U sync[6];if(rd(event_marker_address+sizeof e+sizeof pixels+sizeof alias,sync,sizeof sync))return -1;
    printf("MODULE_SYNC rc=%d created=%u wait=%08x poll=%08x destroy=%u elapsed_us=%u\n",
           (int)sync[0],sync[1],sync[2],sync[3],sync[4],sync[5]);
#endif
#endif
#elif defined(GAIN_TRIAL)
    U obj=e.original-0x675279;
    if(rd(obj+0x1453914,&view,4)||view!=obj+0x14539d8||view!=e.view||
       e.internal!=view||e.slot!=view+0x5c)return -1;
    (void)internal;
#ifdef RECT_TRIAL
    U rectangle[3];
    if(rd(event_marker_address+sizeof e,rectangle,sizeof rectangle))return -1;
    printf("MODULE_RECT phase=%s target=%08x outer=%08x draw_rc=%d\n",phase,rectangle[0],rectangle[1],(int)rectangle[2]);
#ifdef RECT_SERIES_TRIAL
    U series[5];if(rd(event_marker_address+sizeof e+12,series,sizeof series))return -1;
    printf("MODULE_SERIES frames=%u changes=%u percent=%u stopped=%u started_ms=%u\n",series[0],series[1],series[2],series[3],series[4]);
#ifdef RECT_SERVICE_TRIAL
    U health;if(rd(event_marker_address+sizeof e+40,&health,4))return -1;
    printf("MODULE_HEALTH state=%u\n",health);
#endif
    #ifndef RECT_UPLOAD_TRIAL
    if(!strcmp(phase,"after_sample"))valid=valid&&series[3]==1&&series[1]==3;
#endif
#endif
#endif
#ifdef GAIN_SCOPE_TRIAL
    U scope[9];
    if(rd(event_marker_address+sizeof e,scope,sizeof scope))return -1;
    printf("MODULE_GAIN_SCOPE phase=%s outer=%08x delegate=%08x active=%u selector=%u state_active=%u rectangles=%u vertices=%u indices=%u rc=%d\n",
           phase,scope[0],scope[1],scope[2],scope[3],scope[4],scope[5],scope[6],scope[7],(int)scope[8]);
    if(e.captured==1&&scope[8])return -1;
#endif
#else
    U obj=e.original-0x3ef545;
    if(rd(obj+0x1488fdc,&view,4)||view!=e.view||rd(view+0x14,&internal,4)||internal!=e.internal)return -1;
#endif
    printf("MODULE_EVENT phase=%s prepare=%d restore=%d captured=%u capture_rc=%d tid=%u clock=%u.%09u init_tid=%u exit_tid=%u slot=%08x current=%08x original=%08x\n",
           phase,e.prepare_rc,e.restore_rc,e.captured,e.capture_rc,e.tid,e.sec,e.nsec,
           e.init_tid,e.exit_tid,e.slot,current,e.original);
    valid=valid&&!e.prepare_rc;
    #ifdef RECT_UPLOAD_TRIAL
#ifdef RECT_SERVICE_TRIAL
    if(!strcmp(phase,"after_sample"))valid=valid&&(!e.captured||!e.capture_rc);
#else
    if(!strcmp(phase,"after_sample"))valid=valid&&!e.capture_rc;
#endif
#else
    if(!strcmp(phase,"after_sample"))valid=valid&&e.captured==1&&!e.capture_rc&&e.tid&&current==e.original;
#endif
    if(!strcmp(phase,"after_exit"))valid=valid&&!e.restore_rc&&current==e.original;
#endif
#if defined(SCREEN_TRIAL) && !defined(PRESENT_TRIAL) && !defined(RECT_TRIAL)
    int results[2];
    if(rd(base+MARKER_OFFSET+32,results,sizeof results))return -1;
    printf("MODULE_FRAME phase=%s show=%d clear=%d external_redraw=1\n",phase,results[0],results[1]);
    valid=valid&&!results[0]&&!results[1];
    U frame[26];if(rd(base+MARKER_OFFSET+40,frame,sizeof frame))return -1;
    printf("MODULE_FRAME_PIXELS width=%u height=%u attempted=%u target=%08x before=%u after=%u read_rc=%d/%d source_ink=%u source_aa=%u\n",
        frame[0],frame[1],frame[2],frame[19],frame[20],frame[21],(int)frame[22],(int)frame[23],frame[24],frame[25]);
#endif
#if TEXT_TRIAL
    struct text_state t;
    if(rd(base+MARKER_OFFSET,&t,sizeof t))return -1;
    printf("MODULE_TEXT phase=%u load=%d create=%d bounds=%d draw=%d delete=%d unload=%d width=%u height=%u stride=%u bytes=%u guard=%u ink=%u aa=%u transparent=%u\n",
           t.phase,t.load_rc,t.create_rc,t.bounds_rc,t.draw_rc,t.delete_rc,t.unload_rc,
           t.width,t.height,t.stride,t.bytes,t.guard_ok,t.ink,t.aa,t.transparent);
    valid=valid && t.phase==7 && !t.load_rc && !t.create_rc && !t.bounds_rc && !t.draw_rc &&
        !t.delete_rc && !t.unload_rc && t.guard_ok && t.ink && t.aa && t.transparent &&
        t.width && t.width<=128 && t.height==20 && t.stride==t.width*2 && t.bytes==t.stride*t.height && t.bytes<=TEXT_BYTES;
#if TEXT_TRIAL >= 2
    struct managed_state managed;
    if(rd(base+MARKER_OFFSET,&managed,sizeof managed))return -1;
    printf("MODULE_BITMAP stage=%u allocate=%d rect=%d stride_query=%d lock=%d unlock=%d free=%d width=%u height=%u stride=%u padding=%u pool=%08x bitmap=%08x\n",
        managed.stage,managed.allocate_rc,managed.rectangle_rc,managed.stride_rc,managed.lock_rc,
        managed.unlock_rc,managed.free_rc,managed.width,managed.height,managed.stride,
        managed.padding_nonzero,managed.pool,managed.bitmap);
    valid=valid && managed.stage==7 && !managed.allocate_rc && !managed.rectangle_rc && !managed.stride_rc &&
        !managed.lock_rc && !managed.unlock_rc && !managed.free_rc && managed.width==MB_W && managed.height==MB_H &&
        managed.stride==MB_STRIDE && !managed.padding_nonzero && !managed.pool && !managed.bitmap;
#if TEXT_TRIAL >= 3
    struct blit_state b=managed.blit;
    printf("MODULE_BLIT stage=%u allocate=%d rect=%d stride=%d clear_lock=%d clear_unlock=%d submit=%d read_lock=%d read_unlock=%d free=%d compared=%u differences=%u padding=%u pool=%08x bitmap=%08x\n",
        b.stage,b.allocate_rc,b.rectangle_rc,b.stride_rc,b.clear_lock_rc,b.clear_unlock_rc,b.submit_rc,
        b.read_lock_rc,b.read_unlock_rc,b.free_rc,b.compared,b.differences,b.padding_nonzero,b.pool,b.bitmap);
    /* Recovery only after init has returned and both private allocations have
     * been freed. This does not cancel a running native call. */
#if TEXT_TRIAL == 3
    failed_blit_finished=s[0]==0x41374d31 && s[1]==4 && s[2]==1 &&
        s[3]==(!strcmp(phase,"after_exit")?1U:0U) && t.phase==7 && t.draw_rc==-201 &&
        !t.delete_rc && !t.unload_rc && managed.stage==7 && !managed.free_rc &&
        !managed.pool && !managed.bitmap && b.stage==7 && b.allocate_rc &&
        b.submit_rc==-999 && !b.free_rc && !b.pool && !b.bitmap;
#endif
    valid=valid && b.stage==7 && !b.allocate_rc && !b.rectangle_rc && !b.stride_rc && !b.clear_lock_rc &&
        !b.clear_unlock_rc && !b.submit_rc && !b.read_lock_rc && !b.read_unlock_rc && !b.free_rc &&
        b.compared==t.bytes && !b.differences && !b.padding_nonzero && !b.pool && !b.bitmap;
#endif
#endif
    if(valid && !strcmp(phase,"after_exit")) {
        printf("MODULE_TEXT_PIXELS ");
        for(U i=0;i<t.bytes;i++)printf("%02x",t.storage[TEXT_GUARD+i]);
        printf("\n");
    }
#endif
    fflush(0);return valid?0:-1;
}
#ifdef RECT_SERVICE_TRIAL
#include "rect_service_control.h"
#endif
int main(int argc,char **argv) {
    if(argc!=3 || (strcmp(argv[1],"--write-check") && strcmp(argv[1],"--once") &&
                  strcmp(argv[1],"--restore") && strcmp(argv[1],"--inspect-marker")
#ifdef EVENT_TRIAL
                  && strcmp(argv[1],"--finish-event")
#ifdef RECT_SERVICE_TRIAL
                  && strcmp(argv[1],"--capture-frame") && strcmp(argv[1],"--inspect-frame") && strcmp(argv[1],"--service-on") && strcmp(argv[1],"--service-upload") && strcmp(argv[1],"--inspect-service") && strcmp(argv[1],"--service-preview") && strcmp(argv[1],"--service-off") && strcmp(argv[1],"--service-ready") && strcmp(argv[1],"--service-healthy") && strcmp(argv[1],"--service-error")
#endif
#endif
#if TEXT_TRIAL == 3
                  && strcmp(argv[1],"--finish-failed-blit")
#endif
                  ))return 64;
#if TEXT_TRIAL >= 3
    /* 2026-10-23: private two-bitmap trial reached grm_ma/dmm close BUG.
     * Retain read-only inspection/recovery; do not repeat live composition. */
    if(!strcmp(argv[1],"--once")) {
        printf("MODULE_LIVE_DISABLED reason=grm_ma_close_kernel_bug_offline_research_only\n");
        return 84;
    }
#endif
#ifdef RECT_SERVICE_TRIAL
    if(!strcmp(argv[1],"--once"))return 64;
#endif
    char *end=0;unsigned long long pid_value=strtoull(argv[2],&end,10);
    if(!end || *end || pid_value<2 || pid_value>4194304)return 64;
    int pid=(int)pid_value;char *inventory_args[]={argv[0],argv[2],0};
    int rc=inventory_main(2,inventory_args);if(rc)return rc;
#ifdef RECT_UPLOAD_TRIAL
    alarm(90);signal(SIGPIPE,SIG_IGN);
    if((!strcmp(argv[1],"--once")
#ifdef RECT_SERVICE_TRIAL
        ||!strcmp(argv[1],"--service-upload")
#endif
        )&&(dds_upload_bind(&upload_request)||!dds_upload_active(&upload_request)))return 86;
#else
    alarm(25);
#endif
    pinned_base=database_base;path_address=pinned_base+0x60b6;
    char path[64];snprintf(path,sizeof path,"/proc/%d/mem",pid);
    memory=open(path,0);
    if(memory<0 || descriptor_valid())return 73;
#ifdef A7C_SERVICE_LIFECYCLE_ACK
    U im_pending[2];
    if(rd(0x1550c,im_pending,sizeof im_pending))return 73;
    printf("MODULE_IM_PENDING inact=%u act=%u\n",im_pending[0],im_pending[1]);
#endif
#ifdef RECT_SERVICE_TRIAL
    if(!strcmp(argv[1],"--capture-frame")){
        /* Read-only final evidence, also after module retirement. The fixed
         * exclusive file must be archived by the operator before another shot. */
        if(frame_mapping(pid,&frame_base,0))return 87;
        return frame_snapshot(pid,"after",0);
    }
    if(!strcmp(argv[1],"--inspect-frame")){
        U manager[64];if(frame_mapping(pid,&frame_base,0))return 87;
        return frame_source(pid,manager);
    }
    if(!strcmp(argv[1],"--inspect-service"))return marker_state(pid,"after_init")?79:0;
    if(!strcmp(argv[1],"--service-ready")){
        U b=0,table=0,slot=0;
        if(frame_mapping(pid,&b,0)||rd(b+0x1453914,&table,4)||table!=b+0x14539d8||rd(table+0x5c,&slot,4))return 75;
        return loaded()==1?0:slot==b+0x675279?0:75;
    }
    if((!strcmp(argv[1],"--service-on")||!strcmp(argv[1],"--service-off"))&&loaded()==1){
        writer=open(path,2);if(writer<0||marker_state(pid,"after_init"))return 86;
        if(!strcmp(argv[1],"--service-on"))return rect_service_setup(pid)?77:0;
        U zero=0;return pwrite(writer,&zero,4,(long)(event_marker_address+sizeof(struct event_marker)+36))==4&&!rect_upload_publish(0)?0:77;
    }
    if(!strcmp(argv[1],"--service-off"))return loaded()==0?0:77;
    if(!strcmp(argv[1],"--service-healthy")||!strcmp(argv[1],"--service-error")){
        if(loaded()!=1||marker_state(pid,"after_init"))return 86;
        writer=open(path,2);if(writer<0)return 86;
        return rect_service_health(!strcmp(argv[1],"--service-error")?2:1)?77:0;
    }

    if(!strcmp(argv[1],"--service-upload")||!strcmp(argv[1],"--service-preview")){
        writer=open(path,2);if(writer<0||frame_mapping(pid,&frame_base,0)||loaded()!=1||marker_state(pid,"after_init"))return 86;
        return rect_service_upload(pid,!strcmp(argv[1],"--service-preview"));
    }
#endif
    if(!strcmp(argv[1],"--inspect-marker"))return marker_state(pid,"after_exit")?79:0;
#ifdef EVENT_TRIAL
    if(!strcmp(argv[1],"--finish-event")) {
        int pending=loaded();
        if(pending==0)return marker_state(pid,"after_exit")?79:0;
        if(pending!=1||marker_state(pid,"after_init"))return 80;
        int result=send_command(0x940022),checked=marker_state(pid,"after_exit");
        int remaining=refresh(pid)?-1:loaded();
        printf("EVENT_FINISH unload=%d check=%d remaining=%d\n",result,checked,remaining);
        return !result&&!checked&&!remaining?0:81;
    }
#endif
#if TEXT_TRIAL == 3
    if(!strcmp(argv[1],"--finish-failed-blit")) {
        unsigned char original[PATH_BYTES];
        if(path_read_native(original)||memcmp(original,"libIMSample.so",PATH_BYTES)||loaded()!=1)return 80;
        marker_state(pid,"after_init");if(!failed_blit_finished)return 81;
        if(send_command(0x9400e1)!=0x12345678)return 82;
        int done=send_command(0x940022);marker_state(pid,"after_exit");
        int remaining=refresh(pid)?-1:loaded();
        printf("MODULE_FINISH_FAILED_BLIT unload=%d cleanup=%d remaining=%d\n",done,failed_blit_finished,remaining);
        return !done && failed_blit_finished && remaining==0?0:83;
    }
#endif
    writer=open(path,2);if(writer<0)return 73;
    memcpy(tx.original,"libIMSample.so",PATH_BYTES);
    memcpy(tx.replacement,MODULE_PATH,PATH_BYTES);
    tx.read=path_read_native;tx.write=path_write_native;
    if(!strcmp(argv[1],"--restore")) {
        rc=path_restore(&tx);printf("MODULE_RESTORE_ONLY rc=%d\n",rc);return rc;
    }
    unsigned char original[PATH_BYTES];
    if(path_read_native(original)||!path_equal(original,tx.original)||loaded()!=0)return 74;
    if(!strcmp(argv[1],"--write-check")) {
        int written=path_write_native(0,original,PATH_BYTES);
        unsigned char after[PATH_BYTES];
        rc=path_read_native(after)||!path_equal(after,original);
        printf("MODULE_SAME_BYTES wrote=%d unchanged=%d\n",written,!rc);
        return written==PATH_BYTES&&!rc?0:75;
    }
    /* Validate the forked sender's OSAL context before any pathname change. */
    if(send_command(0x9400e1)!=0x12345678)return 78;
#ifdef SCREEN_TRIAL
    if(frame_mapping(pid,&frame_base,0))return 87;
#ifndef RECT_SERVICE_TRIAL
    rc=frame_snapshot(pid,"before",1);if(rc)return rc;
#endif
#endif
    int pipefd[2];if(pipe(pipefd))return 76;
    fflush(0);int guardian=fork();
    if(guardian<0)return 76;
    if(!guardian) {
        close(pipefd[1]);
#ifdef RECT_SERVICE_TRIAL
        alarm(105);int waited=module_guard_wait(pipefd[0],90000);
#elif defined(RECT_UPLOAD_TRIAL)
        alarm(105);int waited=dds_guard_wait(pipefd[0],1,60);
#else
        alarm(32);
        struct poll_fd p={pipefd[0],1,0};int waited=poll(&p,1,20000);
#endif
        int restored=path_restore(&tx);
#ifdef RECT_SERVICE_TRIAL
        if(waited==1){printf("SERVICE_GUARD committed=1 path_restore=%d\n",restored);fflush(0);_exit(restored?1:0);}
        if(waited==MODULE_GUARD_UNKNOWN){
            printf("SERVICE_GUARD outcome=unknown path_restore=%d native_cleanup=skipped\n",restored);
            fflush(0);_exit(2);
        }
#endif
#ifdef EVENT_TRIAL
        int pending=refresh(pid)?-1:loaded();
        int retired=pending==1?send_command(0x940022):pending==0?0:-1;
        printf("EVENT_GUARD pending=%d unload=%d\n",pending,retired);
        if(retired)restored=-1;
#ifdef RECT_SERVICE_TRIAL
        if(pending==1&&!rpc_completed){
            printf("SERVICE_GUARD unload=unknown redraw=skipped\n");fflush(0);_exit(2);
        }
#endif
#endif
#ifdef SCREEN_TRIAL
        int redraw=frame_redraw(pid);if(redraw)restored=redraw;
#endif
        printf("MODULE_GUARD waited=%d restore=%d\n",waited,restored);fflush(0);
        close(pipefd[0]);_exit(restored?1:0);
    }
    close(pipefd[0]);guard_writer=pipefd[1];
    int installed=path_install(&tx),load=-1,restored=-1,unload=-1,observed=-1;
    printf("MODULE_PATH install=%d\n",installed);fflush(0);
    if(!installed)load=send_command(0x940021);
    restored=path_restore(&tx);
    printf("MODULE_PATH restore=%d\n",restored);fflush(0);
#ifdef RECT_SERVICE_TRIAL
    if(!installed&&!rpc_completed)goto unknown_rpc;
#endif
    if(!installed) {
        if(!load)observed=marker_state(pid,"after_init");
#ifdef EVENT_TRIAL
        if(!load&&!observed) {
            int sampled=event_wait(pid);
            if(marker_state(pid,"after_sample")||sampled)observed=-1;
        }
#endif
#ifdef RECT_SERVICE_TRIAL
        if(!load&&!observed){
            int committed=write(guard_writer,"D",1)==1;
            close(guard_writer);guard_writer=-1;int status=0,w=waitpid(guardian,&status,0);
            printf("SERVICE_READY commit=%d guardian=%d installed=%d load=%d restored=%d\n",committed,w==guardian?status:-1,installed,load,restored);fflush(0);
            return committed&&w==guardian&&!status&&!installed&&!load&&!restored?0:77;
        }
#endif
#ifdef RECT_UPLOAD_TRIAL
        if(write(guard_writer,"C",1)!=1)observed=-1;
#endif
#if defined(SCREEN_TRIAL) && !defined(RECT_UPLOAD_TRIAL)
        if(!load&&!observed) {
            /* Capture promptly; the native UI may overwrite a single frame.
             * Waiting is in this external client, never inside im's callback. */
            int captured=frame_snapshot(pid,"during",0);
            if(captured)observed=-1;
            poll(0,0,2000);
        }
#endif
        unload=send_command(0x940022);
#ifdef RECT_SERVICE_TRIAL
        if(!rpc_completed)goto unknown_rpc;
#endif
        if(!unload && marker_state(pid,"after_exit"))observed=-1;
    }
    close(guard_writer);guard_writer=-1;int st=0,w=waitpid(guardian,&st,0);
    int remaining=refresh(pid)?-1:loaded();
#ifdef SCREEN_TRIAL
    int captured=frame_snapshot(pid,"after",0);
    printf("FRAME_AFTER rc=%d\n",captured);
    if(captured)observed=-1;
#endif
    printf("MODULE_DONE install=%d load=%d restore=%d unload=%d marker=%d guardian=%d remaining=%d\n",
           installed,load,restored,unload,observed,w==guardian?st:-1,remaining);fflush(0);
    return !installed&&!load&&!restored&&!unload&&!observed&&w==guardian&&!st&&remaining==0?0:77;
#ifdef RECT_SERVICE_TRIAL
unknown_rpc:
    close(guard_writer);guard_writer=-1;
    {int status=0,joined=waitpid(guardian,&status,0);
     printf("SERVICE_OUTCOME_UNKNOWN install=%d load=%d restore=%d unload=%d guardian=%d native_retry=skipped\n",
            installed,load,restored,unload,joined==guardian?status:-1);fflush(0);}
    return 88;
#endif
}

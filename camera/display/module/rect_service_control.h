/* Controller-side setup and per-upload reuse of the already loaded module.
 * Service indicator itself has no process/pipe/polling loop while idle. */
static int rect_service_setup(int pid){
    char text[32];const char *s=text;U owner;
    if(dds_read_small(DDS_UPLOAD_RAM "worker.pid",text,sizeof text)<0||dds_decimal(&s,&owner)||
       (*s!='\n'&&*s)||owner<2||owner>0x7fffffffU||kill((int)owner,0))return -1;
    U address=event_marker_address+sizeof(struct event_marker)+36;
    if(pwrite(writer,&owner,4,(long)address)!=4||rect_upload_publish(0))return -1;
    (void)pid;
    U observed=0;
    if(rd(address,&observed,4)||observed!=owner)return -1;
    printf("SERVICE_SETUP owner=%u bound=1\n",owner);fflush(0);return 0;
}
static int rect_service_health(unsigned health){
    U address=event_marker_address+sizeof(struct event_marker)+40;
    if(health>2||pwrite(writer,&health,4,(long)address)!=4)return -1;
    U observed=0;
    if(rd(address,&observed,4)||observed!=health)return -1;
    printf("SERVICE_HEALTH state=%u\n",health);fflush(0);return 0;
}
static int rect_service_preview_wait(int pid){
    const U values[3]={20,42,99};U seq=0;int rc=0;
    for(U phase=0;phase<3;phase++)for(U i=0;i<4;i++){
        if(rect_upload_publish((++seq<<8)|128|values[phase])||write(guard_writer,"H",1)!=1){rc=-1;goto done;}
        poll(0,0,500);
        if(phase==1&&i==2&&frame_snapshot(pid,"during",0)){rc=-1;goto done;}
    }
done:if(rect_upload_publish(0))rc=-1;return rc;
}
/* Allow a natural transition first; static photo OSDs need one native redraw.
 * The independent guardian also runs this after controller EOF/termination. */
static int rect_service_return_idle(int pid){
    if(rect_upload_publish(0))return -1;
    for(U i=0;i<40;i++){
        U detail[8];
        if(rd(event_marker_address+sizeof(struct event_marker),detail,sizeof detail)||detail[6])return -1;
        if(detail[3]&&(detail[5]==
#ifdef A7C_SERVICE_NO_IDLE
           101
#else
           100
#endif
           ||detail[5]==102))return 0;
        if(i==10){int redraw=frame_redraw(pid);printf("SERVICE_IDLE_REFRESH result=%d\n",redraw);fflush(0);}
        poll(0,0,50);
    }
    return -1;
}
static int rect_service_upload(int pid,int preview){
    U limit=preview?60:upload_request.limit;alarm(limit+30);
    U detail[10];
    if(rd(event_marker_address+sizeof(struct event_marker),detail,sizeof detail)||detail[6]||
       (!preview&&detail[9]!=upload_request.owner))return 86;
    if(preview&&frame_snapshot(pid,"before",0))return 87;
    int fds[2];if(pipe(fds))return 76;
    fflush(0);int child=fork();if(child<0)return 76;
    if(!child){
        close(fds[1]);alarm(limit+45);dds_guard_wait(fds[0],1,limit);
        int clear=rect_service_return_idle(pid);close(fds[0]);
        printf("SERVICE_UPLOAD_GUARD idle=%d\n",clear);fflush(0);_exit(clear?1:0);
    }
    close(fds[0]);guard_writer=fds[1];
    int rc=preview?rect_service_preview_wait(pid):rect_upload_wait(pid);if(write(guard_writer,"C",1)!=1)rc=-1;
    close(guard_writer);guard_writer=-1;int status=0,w=waitpid(child,&status,0);
    int capture=preview?frame_snapshot(pid,"after",0):0;
    U after[8];int inspect=rd(event_marker_address+sizeof(struct event_marker),after,sizeof after);
    int idle=!inspect&&!after[6]&&(!preview||after[5]==
#ifdef A7C_SERVICE_NO_IDLE
        101
#else
        100
#endif
        );
    printf("SERVICE_UPLOAD_DONE progress=%d guardian=%d capture=%d idle=%d\n",rc,w==child?status:-1,capture,idle);fflush(0);
    return !rc&&w==child&&!status&&!capture&&idle?0:77;
}

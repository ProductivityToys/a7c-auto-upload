/* Runs outside im. Reuses production request parser and progress file.
 * Only a single aligned mailbox word is published to the drawing module.
 * One-shot trial is bounded to 60s; service mode follows the upload deadline. */
static int rect_upload_publish(U word){
    U address=event_marker_address+sizeof(struct event_marker)+32;
    return pwrite(writer,&word,4,(long)address)==4?0:-1;
}
#if defined(RECT_SERVICE_TRIAL) && !defined(RECT_UPLOAD_REDRAW)
#define RECT_UPLOAD_REDRAW rect_upload_redraw
/* frame_redraw while keeping the active guardian's heartbeat alive. Starting
 * the redraw helper (maps scan, attach) can exceed DDS_ACTIVE_WATCHDOG_MS
 * while an upload saturates the CPU; a silent blocking wait made the guardian
 * retire the upload mid-transfer (observed twice, consumer rc 77). Other
 * guardian protocols keep using frame_redraw unchanged. */
static int rect_upload_redraw(int pid){
    if(write(guard_writer,"H",1)!=1)return 91;
    U b=0;if(frame_mapping(pid,&b,0)||b!=frame_base)return 90;
    if(write(guard_writer,"H",1)!=1)return 91;
    fflush(0);int child=fork();if(child<0)return 90;
    if(!child){
        close(guard_writer);
        char pid_arg[16],base_arg[16];snprintf(pid_arg,sizeof pid_arg,"%d",pid);
        snprintf(base_arg,sizeof base_arg,"%x",frame_base);
        char *const argv[]={FRAME_REDRAW,"--request",pid_arg,base_arg,0};
        alarm(8);execv(argv[0],argv);_exit(127);
    }
    int status=0,waited=0,beat_ok=1;U beat=millis();
    for(;;){
        waited=waitpid(child,&status,1 /* WNOHANG */);
        if(waited==child||waited<0)break;
        if(millis()-beat>=500){if(write(guard_writer,"H",1)!=1)beat_ok=0;beat=millis();}
        poll(0,0,50);
    }
    if(waited!=child){status=0;waited=waitpid(child,&status,0);}
    printf("FRAME_REDRAW status=%d heartbeat=%d\n",status,beat_ok);fflush(0);
    if(!beat_ok)return 91;
    return waited==child&&!status?0:90;
}
#endif
static int rect_upload_wait(int pid){
    (void)pid;
    U began=millis(),seq=0,percent=0,last=100;int photographed=0,result=0;
#ifdef RECT_SERVICE_TRIAL
    U refreshed=100;
#endif
    for(;;){
        struct event_marker m;U detail[8];
        if(event_read(&m)||rd(event_marker_address+sizeof m,detail,sizeof detail)){result=-1;break;}
        if(m.capture_rc||detail[6]){result=-1;break;}
        if(!dds_upload_active(&upload_request)){
            printf("RECT_UPLOAD_END reason=request-ended frames=%u percent=%u\n",detail[3],detail[5]);break;
        }
        #ifdef RECT_SERVICE_TRIAL
        if(millis()-began>=upload_request.limit*1000U){printf("RECT_UPLOAD_END reason=request-limit\n");break;}
#else
        if(millis()-began>=55000){printf("RECT_UPLOAD_END reason=trial-limit\n");break;}
#endif
#ifdef RECT_SERVICE_TRIAL
        /* Photo standby can keep a static OSD. Give native redraws one poll
         * to consume the previous value, then request a frame only if stale.
         * Never refresh an unchanged percentage or create an idle timer. */
        if(last<100&&detail[5]!=last&&refreshed!=last){
            int redraw=RECT_UPLOAD_REDRAW(pid);refreshed=last;
            printf("RECT_UPLOAD_REFRESH percent=%u result=%d\n",last,redraw);fflush(0);
            if(redraw==91){result=-1;break;}
        }
#endif
        unsigned incoming;
        if(!progress_for_token(upload_request.token,upload_request.bytes,&incoming)&&incoming>percent)percent=incoming;
        if(rect_upload_publish((++seq<<8)|128U|percent)||write(guard_writer,"H",1)!=1){result=-1;break;}
        if(percent!=last){printf("RECT_UPLOAD_PROGRESS percent=%u\n",percent);fflush(0);last=percent;}
#ifndef RECT_SERVICE_TRIAL
        if(!photographed&&detail[3]&&detail[5]<100){
            int captured=frame_snapshot(pid,"during",0);if(captured){result=-1;break;}photographed=1;
        }
#endif
        poll(0,0,500);
    }
    if(rect_upload_publish(0))result=-1;
    /* The service guardian restores the idle mark, including a static OSD. */
    printf("RECT_UPLOAD_STOP result=%d photographed=%d\n",result,photographed);fflush(0);
    return result;
}

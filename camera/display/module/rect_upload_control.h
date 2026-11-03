/* Runs outside im. Reuses production request parser and progress file.
 * Only a single aligned mailbox word is published to the drawing module.
 * One-shot trial is bounded to 60s; service mode follows the upload deadline. */
static int rect_upload_publish(U word){
    U address=event_marker_address+sizeof(struct event_marker)+32;
    return pwrite(writer,&word,4,(long)address)==4?0:-1;
}
static int rect_upload_wait(int pid){
    (void)pid;
    U began=millis(),seq=0,percent=0,last=100;int photographed=0,result=0;
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
    /* A static UI need not render another frame; module exit also gates and
     * drains the wrapper. Never issue UI queries to manufacture an update. */
    printf("RECT_UPLOAD_STOP result=%d photographed=%d\n",result,photographed);fflush(0);
    return result;
}

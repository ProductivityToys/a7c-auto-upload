/* ILCE-7C 2.00 offline/bounded-trial candidate, not production integration.
 * Core requires an active drawing/state scope on the native drawing thread.
 * Caller pins firmware/context and validates page, size, placement and lifetime.
 * One native transform scope, 4 borders + optional fill, no shared color write.
 * A successful submission is not proof that pixels reached the LCD. */
#if !defined(A7C_RECT_BAR_OFFLINE) && !defined(A7C_RECT_ONCE_TRIAL)
#error Native rectangle bar has not been enabled for camera deployment
#endif
#ifdef A7C_RECT_SERVICE_TRIAL
#define RECT_MAX_PERCENT 102U
#else
#define RECT_MAX_PERCENT 99U
#endif
static int native_rect_bar(U base,void *context,U percent){
    if(!context||percent>RECT_MAX_PERCENT)return -1;
    U *object=context,*methods=(void *)object[0];
    U mode=object[0x348/4];
    if(mode>1||!(((unsigned char *)context)[0x404]&1))return -1;
    const unsigned char white[4]={255,255,255,255};
    U steps=percent*16/100;
    U count=steps?5U:4U;
    H boxes[15][4];
    const H border[5][4]={{562,438,64,6},{562,456,64,6},
                         {562,444,2,12},{624,444,2,12},{564,444,0,12}};
    for(U i=0;i<5;i++)for(U j=0;j<4;j++)boxes[i][j]=border[i][j];
    if(steps)boxes[4][2]=(H)(steps*4-2);
#ifdef A7C_RECT_SERVICE_TRIAL
    if(percent>=100){
        /* Upload arrow above an open tray, final bounds x=20..33, y=447..462.
         * Leave 42px before the native shutter text; progress bar is unchanged. */
        const H icon[7][4]={{578,440,2,2},{576,442,6,2},{574,444,10,2},
                           {578,446,2,6},{572,454,14,2},
                           {572,450,2,4},{584,450,2,4}};
        count=7;
        for(U i=0;i<count;i++)for(U j=0;j<4;j++)boxes[i][j]=icon[i][j];
        if(percent==102){
            for(U i=0;i<4;i++){
                H cross[2][4]={{(H)(590+i*2),(H)(444+i*2),2,2},
                               {(H)(596-i*2),(H)(444+i*2),2,2}};
                for(U k=0;k<2;k++,count++)for(U j=0;j<4;j++)boxes[count][j]=cross[k][j];
            }
        }
    }
    /* Keep the bottom-row baseline, in the empty 64px slot before shutter.
     * Translate the group into x=10..73; only the idle glyph moves left. */
    for(U i=0;i<count;i++){
        boxes[i][0]-=552;
        boxes[i][1]+=(H)(percent>=100?7:5);
    }
#endif
    void (*enter)(void)=(void *)(base+0x671b6d);
    void (*leave)(void)=(void *)(base+0x671b4d);
    int (*submit)(void *,void *)=(void *)(base+0x7e4f19);
    int (*emit)(void *,const unsigned char *,const H *)=(void *)methods[0x7c/4];
    void (*select_mode)(void *,U)=(void *)methods[0xd0/4];
    enter();
    int rc=0;
    for(U i=0;i<count;i++){
        if(!emit(context,white,boxes[i])){rc=-2;break;}
    }
    /* +1c in the original post scope flushes the delegate, not this CPU batch.
     * Submit queued vertices before native post restores graphics state. */
    if(!submit(object+0x2c4/4,(void *)object[4])&&!rc)rc=-3;
    leave();select_mode(context,mode);
    return rc;
}

/* Owned scope for the observed idle gain boundary. Never nest it
 * inside post's state push. Native begin changes viewport outside its saved
 * 13-state block, so restore that separately after native end. */
static int native_rect_bar_owned(U base,void *context,U percent){
    if(!context||percent>RECT_MAX_PERCENT)return -1;
    U *object=context,*methods=(void *)object[0],mode=object[0x348/4];
    unsigned char *delegate=(void *)object[4];
    if(!delegate||mode>1||(((unsigned char *)context)[0x404]&1)||
       delegate[0xa4]||*(H *)((unsigned char *)context+0x326)||
       ((unsigned char *)context)[0x340])return -1;
    const H *view=((const H *(*)(void *))methods[0x4c/4])(context);
    if(!view)return -1;
    H saved[4];for(U i=0;i<4;i++)saved[i]=view[i];
    int (*begin)(void *)=(void *)methods[0x108/4];
    int (*end)(void *)=(void *)methods[0x10c/4];
    if(!begin(context))return -2;
    /* Native begin resets depth state, but leaves the scene's scissor enabled.
     * The observed dirty clip excludes our overlay. Disable only this
     * saved state during emission; native end restores all 13 states. Do not
     * change the scissor rectangle itself or the shared dirty-region globals. */
    ((void (*)(void *,U,U))methods[0x24/4])(context,2,0);
    int rc=native_rect_bar(base,context,percent);
    int ended=end(context);
    ((void (*)(void *,U))methods[0xd0/4])(context,mode);
    if(!ended||(((unsigned char *)context)[0x404]&1))return -4;
    ((void (*)(void *,U,U,U,U))methods[0x48/4])(context,saved[0],saved[1],saved[2],saved[3]);
    return rc;
}

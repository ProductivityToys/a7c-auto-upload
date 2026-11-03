/* Offline-only native rectangle ABI and post-scene ordering proof.
 * No live callback installation, GPU, display, texture or font allocation. */
static unsigned char rect_color[4]={255,255,255,255};
static const H rects[5][4]={{562,438,64,6},{562,456,64,6},
                          {562,444,2,12},{624,444,2,12},{564,444,22,12}};
static U rect_calls,rect_entered;
static void (*rect_native)(int,int,unsigned,unsigned);
static void rect_enter(void){if(rect_entered)bad=1;rect_entered=1;event(11);}
static void rect_leave(void){if(!rect_entered)bad=1;rect_entered=0;event(12);}
static int rect_boundary(void *context,const unsigned char *color,const H *area){
    if(context!=backend||!rect_entered||rect_calls>=5)bad=1;
    if(rect_calls<5)for(U i=0;i<4;i++)if(color[i]!=rect_color[i]||area[i]!=rects[rect_calls][i])bad=1;
    rect_calls++;event(10);return 1;
}
static void rect_callback(void){
    event(7);
    for(U i=0;i<5;i++)rect_native(rects[i][0],rects[i][1],rects[i][2],rects[i][3]);
}
static int rect_contract(U base,void (*post)(void *)){
    if(replace(base+0x671b6c,rect_enter)||replace(base+0x671b4c,rect_leave))return 1;
    rect_native=(void *)(base+0x672319);
    void (*color)(const unsigned char *)=(void *)(base+0x672301);
    color(rect_color);vtable[0x7c/4]=(U)rect_boundary;
    retirement_window=0;count=bad=rect_calls=rect_entered=0;
    native_set_callback(engine,(void *)rect_callback);native_set_enabled(engine,1);
    post(engine);
    if(bad||rect_calls!=5||rect_entered||count!=19||events[0]!=6||events[1]!=7||events[17]!=8||events[18]!=9)return 2;
    for(U i=0;i<5;i++)if(events[2+i*3]!=11||events[3+i*3]!=10||events[4+i*3]!=12)return 3;
    native_set_enabled(engine,0);count=rect_calls=0;post(engine);
    if(count||rect_calls)return 4;
    printf("NATIVE_RECT_POST_OK rectangles=5 geometry=boxed42 color_bytes=4 disabled_no_draw=1 backend_simulated=1\n");
    return 0;
}

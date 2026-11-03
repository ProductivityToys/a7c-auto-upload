/* Execute original DDS refresh and actual TextRM in isolated ARM userspace.
 * Native render entry and logging intercepted; no camera, GPU, timer or hook. */
typedef unsigned U;
typedef unsigned short H;
#define A7C_DDS_REFRESH_OFFLINE 1
#include "../module/dds_native_refresh.h"
#include "dds_progress_payloads.h"
#include "dds_native_reference.h"
extern int printf(const char *,...),mprotect(void *,unsigned,int);
extern void *dlopen(const char *,int),*dlsym(void *,const char *);
extern void __clear_cache(void *,void *);
extern unsigned alarm(unsigned);
static void *native;
static unsigned char state[208];
static struct dds_native_refresh cache;
static U draws,submits,clears,forwards,bad,inject_draw,inject_submit;
static H reference[DDS_NATIVE_PIXELS];
static unsigned char original_render_entry[8];
static int (*load_font)(const char *,U *),(*unload_font)(U);
static int (*create_text)(const char *,U,U,void *,short,U *);
static int (*bounds)(U,void *),(*draw_text)(U,void *,void *,U *),(*delete_text)(U);
static int raster(int percent,H *pixels) {
    draws++;
    if(inject_draw){pixels[0]=0xaaaa;return -31;}
    char label[7]={'U','D',' ',0,0,0,0};U n=3;
    if(percent>=10)label[n++]=(char)('0'+percent/10);
    label[n++]=(char)('0'+percent%10);label[n]='%';
    U font=0,text=0,changed=0,attr[12]={0};
    int rc=load_font("FONT_UNIVERS",&font);if(rc)return rc;
    attr[0]=font;attr[1]=1;attr[2]=(20U<<16)|20;attr[3]=1;attr[4]=0xffffffff;
    rc=create_text(label,0,0x8ff,attr,0,&text);
    if(!rc) {
        struct {H width,height;U stride;} d={0};
        rc=bounds(text,&d);
        if(!rc&&(!d.width||d.width>78||d.height!=20||d.stride!=2U*d.width))rc=-32;
        if(!rc){d.stride=156;rc=draw_text(text,&d,pixels,&changed);}
        int freed=delete_text(text);if(!rc)rc=freed;
    }
    int freed=unload_font(font);return rc?rc:freed;
}
static int submit(const H *pixels,int clear) {
    submits++;if(clear)clears++;
    U ink=0,aa=0;
    for(U i=0;i<DDS_NATIVE_PIXELS;i++) {
        if(pixels[i])ink++;
        U a=pixels[i]&15;if(a&&a<15)aa++;
        if(!clear&&pixels[i]!=reference[i])bad=1;
    }
    if(clear?ink:(!ink||!aa))bad=1;
    return inject_submit?-33:0;
}
static int render(U object,const unsigned char *slots,const H *position) {
    if(object!=(U)(state+4))bad=1;
    int handled=0;
    int rc=dds_native_refresh_run(&cache,slots,position,raster,submit,&handled);
    if(!handled)forwards++;
    /* Native refresh clears +0xcc BEFORE calling this render boundary. If
     * our clear fails, restore that one flag on the same native DDS thread so
     * the next existing refresh retries; never add a timer/retry thread. */
    if(handled&&rc&&cache.owned&&dds_native_percent(slots,position)==-1)
        state[204]=1;
    return rc;
}
static void no_log(void){}
static int replace(U address,void *callback) {
    U page=address&~4095U;if(mprotect((void *)page,8192,7))return 1;
    H *code=(H *)address;code[0]=0xf8df;code[1]=0xf000|(address&2);
    unsigned char *p=(void *)(address+4);U dest=(U)callback;
    for(U i=0;i<4;i++)p[i]=dest>>(8*i);
    __clear_cache((void *)address,(void *)(address+8));
    return mprotect((void *)page,8192,5)!=0;
}
static void payload(U percent) {
    state[18]=1;state[20]=5;
    for(U i=0;i<8;i++)state[22+i]=progress_payloads[percent][i];
}
/* Keep native admission query and allocate/raster/submit/free ordering.
 * Only boundaries are simulated; no inference about the query's units. */
static U pipeline_mode,pipeline_count;
static char pipeline_events[16];
static void pe(char c){pipeline_events[pipeline_count++]=c;pipeline_events[pipeline_count]=0;}
static int query(U queue,U *request) {
    pe('Q');if(queue!=0x00910042||request[0]!=0x20||request[4]!=1)bad=1;
    if(pipeline_mode==8)return -8;
    request[6]=pipeline_mode==0?0:pipeline_mode==1?19999999:20000000;
    request[7]=pipeline_mode==3?1:0;
    return 0;
}
static int allocate(U object,U *pool,void **bitmap) {
    pe('A');if(object!=123)bad=1;
    if(pipeline_mode==4)return -41;
    *pool=77;*bitmap=(void *)88;return 0;
}
static int pipeline_raster(U object,const void *slots,void *bitmap) {
    pe('R');if(object!=123||slots!=state||bitmap!=(void *)88)bad=1;
    return pipeline_mode==5?-42:0;
}
static int pipeline_submit(U object,U pool,void *bitmap,const void *position) {
    pe('S');if(object!=123||pool!=77||bitmap!=(void *)88||position!=state+200)bad=1;
    return pipeline_mode==6?-43:0;
}
static int cleanup(U object,U pool,void *bitmap) {
    pe('F');if(object!=123||pool!=(pipeline_mode==4?0U:77U)||bitmap!=(void *)(pipeline_mode==4?0U:88U))bad=1;
    return pipeline_mode==7?-44:0;
}
static int pipeline(U base) {
    U address=base+0x7db5a8,page=address&~4095U;
    if(mprotect((void *)page,8192,7))return 1;
    for(U i=0;i<8;i++)((unsigned char *)address)[i]=original_render_entry[i];
    __clear_cache((void *)address,(void *)(address+8));
    if(mprotect((void *)page,8192,5))return 2;
    /* This PLT is ARM, not Thumb. Replace its entry with an ARM literal jump. */
    address=base+0x10c138;page=address&~4095U;
    if(mprotect((void *)page,4096,7))return 3;
    ((U *)address)[0]=0xe51ff004;((U *)address)[1]=(U)query;
    __clear_cache((void *)address,(void *)(address+8));
    if(mprotect((void *)page,4096,5))return 4;
    if(replace(base+0x7db2d0,allocate)||replace(base+0x7db4a0,pipeline_raster)||
       replace(base+0x7db518,pipeline_submit)||replace(base+0x7db568,cleanup))return 5;
    int (*original)(U,const void *,const void *)=(void *)(base+0x7db5a9);
    const char *orders[]={"Q","Q","QARSF","QARSF","QAF","QARF","QARSF","QARSF","Q"};
    const int returns[]={0,0,0,0,-41,-42,-43,0,0};
    for(pipeline_mode=0;pipeline_mode<9;pipeline_mode++) {
        pipeline_count=0;pipeline_events[0]=0;
        int rc=original(123,state,state+200);
        const char *expected=orders[pipeline_mode];
        for(U i=0;expected[i]||pipeline_events[i];i++)if(expected[i]!=pipeline_events[i])bad=1;
        printf("DDS_PIPELINE mode=%u rc=%d events=%s bad=%u\n",pipeline_mode,rc,pipeline_events,bad);
        if(bad||rc!=returns[pipeline_mode])return 6;
    }
    printf("NATIVE_DDS_PIPELINE_OK 9 admission_gate_preserved cleanup_order_verified\n");
    return 0;
}
int main(void) {
    alarm(15);native=dlopen("/lab/libObj.so",1);if(!native)return 1;
    load_font=dlsym(native,"TextRM_loadFont");if(!load_font)return 2;
    U base=(U)load_font-0x57d271;
    int (*init)(void)=(void *)(base+0x57d8b9);
    if(init())return 3; /* isolated lab only; never initialize camera runtime */
    unload_font=dlsym(native,"TextRM_unloadFont");create_text=dlsym(native,"TextRM_createText");
    bounds=dlsym(native,"TextRM_getBounds");draw_text=dlsym(native,"TextRM_drawText");
    delete_text=dlsym(native,"TextRM_deleteText");
    if(!unload_font||!create_text||!bounds||!draw_text||!delete_text)return 4;
    for(U i=0;i<8;i++)original_render_entry[i]=((unsigned char *)(base+0x7db5a8))[i];
    if(replace(base+0x7db5a8,render)||replace(base+0x7daff0,no_log)||replace(base+0x7db060,no_log))return 5;
    int (*refresh)(void *)=(void *)(base+0x7db76d);
    state[200]=562&255;state[201]=562>>8;state[202]=432&255;state[203]=432>>8;
    /* Actual original refresh must do no rendering while idle. */
    if(refresh(state)||submits||draws||forwards)return 6;
    for(U p=0;p<100;p++) {
        for(U i=0;i<DDS_NATIVE_PIXELS;i++)reference[i]=0;
        if(raster(p,reference))return 7;
        if(p==42)for(U y=0;y<20;y++)for(U x=0;x<78;x++) {
            H expected=x<71?native_reference[y*71+x]:0;
            if(reference[y*78+x]!=expected)return 25;
        }
        U before=draws;payload(p);
        for(U repeat=0;repeat<3;repeat++)if(refresh(state))return 8;
        if(bad||draws!=before+1||cache.percent!=(int)p||!state[204])return 9;
    }
    if(submits!=300||forwards||draws!=200)return 10;
    printf("DDS_NATIVE_REFRESH all_progress=100 refreshes=300 generated=100 cache_hits=200 aa_preserved=1\n");
    /* Foreign slots/payload/color/position go to original renderer untouched. */
    U before=submits;
    state[42]=1;state[44]=5;
    if(refresh(state))return 11;state[42]=0;
    state[22]=0x12;if(refresh(state))return 12;payload(99); /* noncanonical leading zero */
    state[20]=4;if(refresh(state))return 13;state[20]=5;
    state[200]++;if(refresh(state))return 14;state[200]--;
    state[29]=1;if(refresh(state))return 15;state[29]=0;
    if(forwards!=5||submits!=before)return 16;
    /* Disabled native payload bytes are deliberately poisoned. */
    state[18]=0;for(U i=0;i<8;i++)state[22+i]=0xee;
    if(refresh(state)||cache.owned||cache.valid||state[204]||clears!=1)return 17;
    before=submits;for(U i=0;i<10;i++)if(refresh(state))return 18;
    if(submits!=before)return 19;
    /* Faults: no partial raster submitted, successful raster reused on retry. */
    payload(42);inject_draw=1;
    if(refresh(state)!=-31||cache.valid||submits!=before)return 20;
    inject_draw=0;inject_submit=1;
    for(U i=0;i<DDS_NATIVE_PIXELS;i++)reference[i]=0;
    if(raster(42,reference))return 21;
    if(refresh(state)!=-33||!cache.valid||cache.owned)return 22;
    U generated=draws;inject_submit=0;
    if(refresh(state)||draws!=generated||!cache.owned||bad)return 23;
    state[18]=0;inject_submit=1;
    if(refresh(state)!=-33||!cache.owned||!state[204]||clears!=2)return 24;
    inject_submit=0;
    if(refresh(state)||cache.owned||state[204]||clears!=3||bad)return 26;
    before=submits;if(refresh(state)||submits!=before)return 27;
    printf("NATIVE_DDS_REFRESH_OK foreign=5 clear_once=1 idle_no_render=1 raster_failure=1 submit_retry=1 clear_retry_existing_tick=1 reference_pixels_exact=1 cache_bytes=%u\n",(U)sizeof cache);
    return pipeline(base)?28:0;
}

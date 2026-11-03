/* ILCE-7C 2.00 read-only frame-context snapshot. Host verifies firmware hash.
 * No native calls, IPC, load/unload, writable fd, hook, pixel or state writes.
 * An unlocked snapshot is diagnostic evidence, never installation authority. */
#define main inventory_main
#define IM_NATIVE_PHASE 1
#include "../im_modules.c"
#undef main
#include "native_phase_snapshot.h"
static int targets(U base,U delegate) {
    /* Read native-window/surface identities, not pixels. Constructor 7e727c
     * preserves the window at +164 and creates the surface at +16c. Native
     * surface handle conversion 78c7e0/78c7f0 is the identity operation. */
    U handles[4],surface[29],window[12],window_ops[12],wrapper[4];
    U manager=base+0x1453df0,guard,count,front,bitmap[3],descriptor[10],after[2];
    if(rd(delegate+0x164,handles,sizeof handles)||!handles[0]||!handles[2]||
       rd(handles[2],surface,sizeof surface)||surface[2]!=1||
       surface[0x6c/4]!=handles[0]||!surface[0x70/4]||
       rd(surface[0x70/4],wrapper,sizeof wrapper)||wrapper[0]!=1||wrapper[3]!=handles[0]||
       rd(handles[0],window,sizeof window)||window[1]!=0xcefacade||
       rd(window[0],window_ops,sizeof window_ops)||
       rd(base+0x1453de8,&guard,4)||!(guard&1)||
       rd(manager+0x58,&count,4)||count<1||count>16||
       rd(manager+0x8c,&front,4)||!front||rd(front,bitmap,sizeof bitmap)||
       rd(bitmap[1],descriptor,sizeof descriptor)||
       rd(base+0x145abe4,after,sizeof after))return 75;
    printf("FRAME_TARGET window=%08x display=%08x surface=%08x context=%08x front=%08x same_object=%u\n",
           handles[0],handles[1],handles[2],handles[3],front,handles[0]==front);
    printf("SURFACE_ID window=%08x wrapper=%08x wrapper_window=%08x width=%u height=%u\n",
           surface[0x6c/4],surface[0x70/4],wrapper[3],surface[0x34/4],surface[0x30/4]);
    printf("DDS_FRONT vtable=%08x descriptor=%08x pixels=%08x dimensions=%08x stride_dimensions=%08x format=%u physical=%08x count=%u\n",
           bitmap[0],bitmap[1],bitmap[2],descriptor[4],descriptor[6],descriptor[7],descriptor[9],count);
    for(U i=0;i<12;i++)printf("NATIVE_WINDOW offset=%02x word=%08x method=%08x\n",i*4,window[i],window_ops[i]);
    printf("AFTER_PRESENT callback=%08x argument=%08x\n",after[0],after[1]);
    /* Window getters 75b50c/75b5a0 resolve a resource at window+58, whose
     * vector is another +58 and current index +64. Entries are two words;
     * 75b2fa computes (end-begin)/8 and 75b3fe indexes begin+index*8. */
    U vector[4];
    if(window[0]!=base+0x13b3da0||rd(handles[0]+0xb0,vector,sizeof vector)||
       vector[1]<vector[0]||vector[1]-vector[0]>16*8||
       ((vector[1]-vector[0])&7)||vector[3]>=(vector[1]-vector[0])/8)return 77;
    U entries=(vector[1]-vector[0])/8;
    printf("WINDOW_BUFFERS begin=%08x end=%08x count=%u current=%u\n",vector[0],vector[1],entries,vector[3]);
    for(U i=0;i<entries;i++) {
        U item[2],header[3],methods[21];
        if(rd(vector[0]+i*8,item,sizeof item))return 77;
        printf("WINDOW_BUFFER index=%u object=%08x resource_id=%08x same_front=%u\n",i,item[0],item[1],item[0]==front);
        if(!item[0])continue; /* Lazy native resolution is not called here. */
        if(rd(item[0],header,sizeof header)||rd(header[0],methods,sizeof methods))return 77;
        printf("WINDOW_BITMAP vtable=%08x word04=%08x word08=%08x rectangle=%08x format=%08x pixels_method=%08x\n",
               header[0],header[1],header[2],methods[0x14/4],methods[0x20/4],methods[0x4c/4]);
    }
    U again[4],last_front,last_surface_window;
    if(rd(delegate+0x164,again,sizeof again)||memcmp(again,handles,sizeof handles)||
       rd(manager+0x8c,&last_front,4)||last_front!=front||
       rd(handles[2]+0x6c,&last_surface_window,4)||last_surface_window!=handles[0])return 76;
    if(rd(handles[0]+0xb0,again,sizeof again)||memcmp(again,vector,sizeof vector))return 76;
    return 0;
}
static int import_pointers(U base) {
    /* Read only: these entries are ARM ELF JUMP_SLOT data, not code bytes.
     * A match here does not grant writable mapping or live installation. */
    const U offsets[3]={0x13cf13c,0x13d08dc,0x13d0640};
    const U expected[3]={0x68dc29,0x68dc39,0x68ce03};
    U before[3],after[3];
    for(U i=0;i<3;i++) {
        if(rd(base+offsets[i],before+i,4))return 78;
        printf("DDS_IMPORT index=%u slot=%08x target=%08x expected=%08x resolved=%u\n",
               i,base+offsets[i],before[i],base+expected[i],before[i]==base+expected[i]);
    }
    U life[7];unsigned char state[208];
    if(rd(base+0x145aac8,life,sizeof life)||rd(base+0x145aae4,state,sizeof state))return 78;
    printf("DDS_IMPORT_STATE timer=%08x first=%u slot0=%u visible=%u x=%u y=%u\n",
        life[3],life[4],state[18],state[204],state[200]|((U)state[201]<<8),state[202]|((U)state[203]<<8));
    for(U i=0;i<3;i++)if(rd(base+offsets[i],after+i,4)||before[i]!=after[i])return 79;
    return 0;
}
static int rectangle_backend(U outer,U delegate) {
    /* Passive resource/state inventory. Do not call readiness getters: those
     * can compile/bind resources. This snapshot is outside the draw callback. */
    U data[0x154/4],queue[0x84/4],again;
    if(rd(delegate,data,sizeof data)||rd(outer+0x2c4,queue,sizeof queue))return 80;
    printf("RECT_BACKEND outside_draw=1 state_active=%u vertex=%08x vertex_dirty=%u index=%08x index_dirty=%u layout=%08x layout_dirty=%u shader=%08x shader_dirty=%u previous_shader=%08x\n",
        (data[0xa4/4]&255),data[0x118/4],data[0x11c/4]&255,
        data[0x124/4],data[0x128/4]&255,data[0x130/4],data[0x134/4]&255,
        data[0x13c/4],data[0x140/4]&255,data[0x144/4]);
    for(U i=0;i<13;i++)printf("RECT_STATE index=%u value=%08x\n",i,data[0x2c/4+i]);
    printf("RECT_CLIP enabled=%u gl_xy=%08x gl_wh=%08x viewport_xy=%08x viewport_wh=%08x render_target=%08x target_dirty=%u target_previous=%08x\n",
        data[0x34/4],data[0x60/4],data[0x64/4],data[0xa8/4],data[0xac/4],
        data[0x148/4],data[0x14c/4]&255,data[0x150/4]);
    for(U i=0;i<8;i++)printf("RECT_TEXTURE index=%u object=%08x dirty=%u previous=%08x\n",
        i,data[0xb8/4+3*i],data[0xbc/4+3*i]&255,data[0xc0/4+3*i]);
    printf("RECT_QUEUE rectangles=%u vertices=%u indices=%u mapped=%u vertex0=%08x vertex1=%08x index0=%08x index1=%08x layout0=%08x layout1=%08x shader=%08x\n",
        (queue[0x60/4]>>16),queue[0x4c/4],queue[0x58/4],queue[0x7c/4]&255,
        queue[1],queue[2],queue[3],queue[4],queue[5],queue[6],queue[7]);
    const U objects[5]={data[0x118/4],data[0x124/4],data[0x130/4],data[0x13c/4],queue[7]};
    const char *names[5]={"vertex","index","layout","bound_shader","queue_shader"};
    for(U i=0;i<5;i++){
        U header[8],methods[22];
        if(!objects[i])continue;
        if(rd(objects[i],header,sizeof header)||rd(header[0],methods,sizeof methods)){
            printf("RECT_RESOURCE name=%s object=%08x readable=0\n",names[i],objects[i]);continue;
        }
        printf("RECT_RESOURCE name=%s object=%08x vtable=%08x method40=%08x method4c=%08x header=",
            names[i],objects[i],header[0],methods[0x40/4],methods[0x4c/4]);
        for(U j=1;j<8;j++)printf("%08x%s",header[j],j==7?"\n":":");
    }
    if(rd(outer+0x10,&again,4)||again!=delegate)return 81;
    printf("RECT_BACKEND_END snapshot_not_locked=1 readiness_not_called=1\n");
    return 0;
}
static int snapshot(U base) {
    int imports_rc=import_pointers(base);if(imports_rc)return imports_rc;
    U magic,view,internal,engine,backend,table,callbacks[2],ops[16],again,event_handler,event_code[4];
    unsigned char flags[4],code[10];
    static const unsigned char setter[10]={0x80,0xb5,0x00,0xaf,0xc0,0xf8,0x2c,0x12,0x80,0xbd};
    if(rd(base,&magic,4)||magic!=0x464c457f||
       rd(base+0x61805a,code,10)||memcmp(code,setter,10))return 68;
    if(rd(base+0x1488fdc,&view,4)||!view||rd(view+0x14,&internal,4)||!internal||
       rd(internal+0x10,&engine,4)||!engine||
       rd(internal+0x14,&event_handler,4)||!event_handler||
       rd(event_handler&~1U,event_code,sizeof event_code)||
       rd(engine+0x228,callbacks,8)||rd(engine+0x230,flags,4)||
       rd(base+0x1453918,&backend,4)||!backend||rd(backend,&table,4)||
       rd(table,ops,sizeof ops))return 69;
    printf("FRAME_CONTEXT base=%08x view=%08x internal=%08x engine=%08x backend=%08x vtable=%08x\n",
           base,view,internal,engine,backend,table);
    printf("FRAME_CALLBACK pre=%08x post=%08x pre_enabled=%u post_enabled=%u prepared=%u\n",
           callbacks[0],callbacks[1],flags[0],flags[1],flags[2]);
    printf("FRAME_EVENT handler=%08x entry=%08x:%08x:%08x:%08x\n",
           event_handler,event_code[0],event_code[1],event_code[2],event_code[3]);
    /* GraphicsSystem dispatch 0x66de3c loads table+0x5c once. Read the exact
     * callback table separately from GraphicsEngine and context vtables. */
    U system_table,system_ops[25],gain_code[4];
    if(rd(base+0x1453914,&system_table,4)||!system_table||
       rd(system_table,system_ops,sizeof system_ops)||!system_ops[0x5c/4]||
       rd(system_ops[0x5c/4]&~1U,gain_code,sizeof gain_code))return 73;
    printf("GRAPHICS_SYSTEM table=%08x expected_table=%08x begin=%08x gain=%08x expected_gain=%08x\n",
           system_table,base+0x14539d8,system_ops[0x0c/4],system_ops[0x5c/4],base+0x675279);
    printf("GRAPHICS_GAIN_ENTRY %08x:%08x:%08x:%08x\n",
           gain_code[0],gain_code[1],gain_code[2],gain_code[3]);
    for(U i=0;i<16;i++)printf("BACKEND_SLOT offset=%02x target=%08x\n",i*4,ops[i]);
    /* This exact 2.00 wrapper forwards +18/+1c/+2c/+30 to object +0x10.
     * Read one verified delegation level, not an arbitrary pointer walk. */
    U delegate,delegate_table,delegate_ops[16];
    if(table!=base+0x13b68c0||ops[0x2c/4]!=base+0x7ec745||
       ops[0x30/4]!=base+0x7ec70d||ops[0x1c/4]!=base+0x7ec7b9||
       rd(backend+0x10,&delegate,4)||!delegate||rd(delegate,&delegate_table,4)||
       rd(delegate_table,delegate_ops,sizeof delegate_ops))return 71;
    printf("FRAME_DELEGATE object=%08x vtable=%08x\n",delegate,delegate_table);
    for(U i=0;i<16;i++)printf("DELEGATE_SLOT offset=%02x target=%08x\n",i*4,delegate_ops[i]);
    if(delegate_table!=base+0x13b6648||delegate_ops[0x18/4]!=base+0x7e6935)return 75;
    int target_rc=targets(base,delegate);if(target_rc)return target_rc;
    int rectangle_rc=rectangle_backend(backend,delegate);if(rectangle_rc)return rectangle_rc;
    if(rd(backend+0x10,&again,4)||again!=delegate||
       rd(delegate,&again,4)||again!=delegate_table)return 72;
    if(rd(base+0x1453914,&again,4)||again!=system_table||
       rd(system_table+0x5c,&again,4)||again!=system_ops[0x5c/4])return 74;
    if(rd(base+0x1488fdc,&again,4)||again!=view||rd(view+0x14,&again,4)||again!=internal||
       rd(internal+0x10,&again,4)||again!=engine||
       rd(internal+0x14,&again,4)||again!=event_handler||
       rd(base+0x1453918,&again,4)||again!=backend||rd(backend,&again,4)||again!=table)return 70;
    printf("FRAME_CONTEXT_END identity_unchanged=1 snapshot_not_locked=1\n");
    return 0;
}
int main(int argc,char **argv) {
    int burst=argc==4&&!strcmp(argv[3],"--native-phase-burst");
    alarm(burst?10:5);if(argc!=3 && !(argc==4&&(!strcmp(argv[3],"--native-phase")||burst)))return 64;
    char *end=0,path[64],exe[128];
    unsigned long long pid=strtoull(argv[1],&end,10);
    if(!end||*end||pid<2||pid>4194304)return 64;
    unsigned long long base=strtoull(argv[2],&end,16);
    if(!end||*end||base<0x1000000||base>0x30000000||(base&4095))return 64;
    snprintf(path,sizeof path,"/proc/%u/exe",(U)pid);
    int n=readlink(path,exe,sizeof exe-1);if(n<=0||n==(int)sizeof exe-1)return 65;
    exe[n]=0;if(strcmp(exe,"/usr/bin/im.elf"))return 65;
    if(get_maps((int)pid))return 66;
    snprintf(path,sizeof path,"/proc/%u/mem",(U)pid);
    memory=open(path,0);if(memory<0)return 67;
    int rc=burst?native_phase_burst((U)base):argc==4?native_phase_snapshot((U)base):snapshot((U)base);close(memory);return rc;
}

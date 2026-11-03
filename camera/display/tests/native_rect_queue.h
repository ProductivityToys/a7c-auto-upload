/* Real Sony vertex/index generation and batch submission, isolated ARM.
 * Buffer objects, shader and final GPU methods are synthetic; no driver. */
static U queue_vtable[16],queue_itable[16],queue_dtable[64],queue_stable[24];
static U queue_vbuffer[2],queue_ibuffer[2],queue_shader[1];
#ifdef NATIVE_RECT_SERVICE_CONTRACT
/* The 1000-redraw ablation intercepts GPU completion, so no real driver rotates
 * its backing buffers. Reserve the full run here: native ring rollover is a
 * separate contract, not part of idle submission counting. */
static U queue_vertices[454096],queue_indices[22024];
#else
static U queue_vertices[4096],queue_indices[1024];
#endif
static U queue_draws,queue_stage,queue_vertices_set,queue_indices_set;
static H queue_viewport[4]={0,0,640,480};
static U *queue_state;
static U queue_no_flush;
#ifdef NATIVE_RECT_SERIES_CONTRACT
static U queue_expected_percent=42;
#endif
static U queue_gpu_result;

static int rect_owned_scope_contract(U base);
static int queue_rc;
static U queue_vertex_offset,queue_index_offset;
static int queue_map(U *buffer,U offset,U size,U **out){
    U *storage=buffer==queue_vbuffer?queue_vertices:queue_indices;
    U capacity=buffer==queue_vbuffer?sizeof queue_vertices:sizeof queue_indices;
    if((buffer!=queue_vbuffer&&buffer!=queue_ibuffer)||offset>capacity||size>capacity-offset){bad=1;return 0;}
    if(buffer==queue_vbuffer)queue_vertex_offset=offset;else queue_index_offset=offset;
    *out=(void *)((unsigned char *)storage+offset);return 1;
}
static int queue_unmap(U *buffer){if(buffer!=queue_vbuffer&&buffer!=queue_ibuffer)bad=1;return 1;}
static U queue_vstride(void *p){if(p!=queue_vbuffer)bad=1;return 64;}
static U queue_vcapacity(void *p){if(p!=queue_vbuffer)bad=1;return sizeof queue_vertices;}
static U queue_istride(void *p){if(p!=queue_ibuffer)bad=1;return 2;}
static U queue_itype(void *p){if(p!=queue_ibuffer)bad=1;return 1;}
static U queue_icapacity(void *p){if(p!=queue_ibuffer)bad=1;return sizeof queue_indices;}
static void queue_vcount(void *p,U n){if(p!=queue_vbuffer)bad=1;queue_vertices_set=n;}
static void queue_icount(void *p,U n){if(p!=queue_ibuffer)bad=1;queue_indices_set=n;}
static void queue_bind_v(void *p,void *v){if(p!=delegate||v!=queue_vbuffer)bad=1;}
static void queue_bind_i(void *p,void *v){if(p!=delegate||v!=queue_ibuffer)bad=1;}
static void queue_layout(void *p,U v){if(p!=delegate||v!=0x1234)bad=1;}
static void queue_bind_shader(void *p,void *v){if(p!=delegate||v!=queue_shader)bad=1;}
static H *queue_view(void *p){if(p!=delegate)bad=1;return queue_viewport;}
static void queue_shader_setup(void *shader,void *context,U sx,U sy){
    if(shader!=queue_shader||context!=delegate||!sx||!sy)bad=1;
}
static U float_bits(U n){union {float f;U u;} v;v.f=(float)n;return v.u;}
static int queue_submit(void *context,U mode,U offset,U count){
    U rectangles=5;
#ifdef NATIVE_RECT_SERVICE_CONTRACT
    if(queue_service_alignment&&queue_expected_percent>=100)rectangles=queue_expected_percent==102?15:7;
#endif
    U indices=rectangles*6-2;
    if(context!=delegate||mode!=4||offset!=queue_index_offset||count!=indices||
       queue_vertices_set!=rectangles*4||queue_indices_set!=indices||queue_stage!=1)bad=1;
    /* One quad per rectangle, four 64-byte vertices each. Sony code preserves
     * positions, white RGBA and the copied 2-D identity transform. */
    for(U r=0;r<rectangles;r++)for(U v=0;v<4;v++){
        U *vertex=queue_vertices+queue_vertex_offset/4+(r*4+v)*16;
        const H *expected_rect=rects[r<5?r:0];
#ifdef NATIVE_RECT_SERVICE_CONTRACT
        const H icon[7][4]={{578,440,2,2},{576,442,6,2},{574,444,10,2},{578,446,2,6},{572,454,14,2},{572,450,2,4},{584,450,2,4}};
        H cross[4];
        if(queue_expected_percent>=100){
            if(r<7)expected_rect=icon[r];
            else {
                U i=(r-7)/2;
                cross[0]=(H)((r-7)%2?596-i*2:590+i*2);
                cross[1]=(H)(444+i*2);cross[2]=cross[3]=2;
                expected_rect=cross;
            }
        }
#endif
        U width=expected_rect[2];
#ifdef NATIVE_RECT_SERIES_CONTRACT
        if(r==4&&queue_expected_percent<100)width=4*(queue_expected_percent*16/100)-2;
#endif
        U x=expected_rect[0]+(v>=2?width:0);
        U y=expected_rect[1]+((v==1||v==3)?expected_rect[3]:0);
#ifdef NATIVE_RECT_SERVICE_CONTRACT
        if(queue_service_alignment){x-=552;y+=queue_expected_percent>=100?7:5;}
#endif
        if(vertex[0]!=float_bits(x)||vertex[1]!=float_bits(y)||vertex[2]!=0x3f800000)bad=1;
        for(U c=3;c<7;c++)if(vertex[c]!=0x3f800000)bad=1;
        const U transform[6]={0x3f800000,0,0,0,0x3f800000,0};
        for(U c=0;c<6;c++)if(vertex[9+c]!=transform[c])bad=1;
    }
    U index=0;H *actual=(H *)queue_indices+queue_index_offset/2;
    for(U r=0;r<rectangles;r++){
        if(r){
            if(actual[index++]!=r*4-1+queue_vertex_offset/64)bad=1;
            if(actual[index++]!=r*4+queue_vertex_offset/64)bad=1;
        }
        for(U v=0;v<4;v++)if(actual[index++]!=r*4+v+queue_vertex_offset/64)bad=1;
    }
    queue_draws++;return (int)queue_gpu_result;
}
static void queue_callback(void){
    if(queue_no_flush){
        void (*enter)(void)=(void *)(rect_bar_base+0x671b6d);
        void (*leave)(void)=(void *)(rect_bar_base+0x671b4d);
        int (*emit)(void *,const unsigned char *,const H *)=(void *)rect_vtable[0x7c/4];
        enter();for(U i=0;i<5;i++)emit(rect_context,rect_color,rects[i]);leave();
    }else queue_rc=native_rect_bar(rect_bar_base,rect_context,42);
}
static int rect_queue_contract(U base,void (*post)(void *)){
    queue_state=rect_context+0x2c4/4;
    for(U i=0;i<64;i++)queue_dtable[i]=((U *)(base+0x13b6648))[i];
    delegate[0]=(U)queue_dtable;
    queue_dtable[0xb0/4]=(U)queue_bind_v;queue_dtable[0xa8/4]=(U)queue_bind_i;
    queue_dtable[0xb8/4]=(U)queue_layout;queue_dtable[0xbc/4]=(U)queue_bind_shader;
    queue_dtable[0x4c/4]=(U)queue_view;queue_dtable[0xe0/4]=(U)queue_submit;
    queue_vbuffer[0]=(U)queue_vtable;queue_ibuffer[0]=(U)queue_itable;
    queue_shader[0]=(U)queue_stable;queue_stable[0x54/4]=(U)queue_shader_setup;
    queue_vtable[3]=(U)queue_map;queue_vtable[4]=(U)queue_unmap;
    queue_vtable[7]=(U)queue_vstride;queue_vtable[8]=(U)queue_vcapacity;queue_vtable[9]=(U)queue_vcount;
    queue_itable[3]=(U)queue_map;queue_itable[4]=(U)queue_unmap;
    queue_itable[7]=(U)queue_itype;queue_itable[8]=(U)queue_istride;
    queue_itable[9]=(U)queue_icapacity;queue_itable[10]=(U)queue_icount;
    rect_vtable[0x7c/4]=base+0x7ecf9d;
    native_set_callback(engine,(void *)queue_callback);
    int (*submit)(void *,void *)=(void *)(base+0x7e4f19);
    for(U scenario=0;scenario<3;scenario++){
        for(U i=0;i<0x84/4;i++)queue_state[i]=0;
        queue_state[1]=queue_state[2]=(U)queue_vbuffer;
        queue_state[3]=queue_state[4]=(U)queue_ibuffer;
        queue_state[5]=queue_state[6]=0x1234;queue_state[7]=(U)queue_shader;
        queue_state[0x44/4]=1;
        for(U i=0;i<13;i++)delegate[0x28/4+1+i]=100+i;
        ((unsigned char *)rect_context)[0x404]=1;rect_context[0x348/4]=0;
        bad=restored=rect_state_flushes=queue_draws=queue_vertices_set=queue_indices_set=0;
        queue_no_flush=scenario==0;queue_gpu_result=scenario!=2;queue_stage=1;post(engine);
        if(bad||restored!=13||rect_state_flushes!=1)return 1;
        if(!scenario){
            if(queue_draws||((H *)queue_state)[0x62/2]!=5)return 2;
            if(submit(queue_state,delegate)!=1||bad||queue_draws!=1)return 3;
        }else if(queue_rc||queue_draws!=1||bad)return 4;
        if(((H *)queue_state)[0x62/2]||((unsigned char *)queue_state)[0x7c]||queue_state[0x50/4]||queue_state[0x5c/4])return 5;
        if(submit(queue_state,delegate)!=1||queue_draws!=1)return 6;
    }
    int owned_rc=rect_owned_scope_contract(base);if(owned_rc)return 20+owned_rc;
    delegate[0]=base+0x13b6648;
    printf("NATIVE_RECT_QUEUE_OK native_vertex_index=1 vertices=20 indices=28 post_alone_leaves_pending=1 explicit_submit=1 batch_cleared=1 empty_submit_no_draw=1 native_discards_gpu_result=1 gpu_simulated=1\n");
    return 0;
}

static U scope_view_sets,scope_state_sets;
static void scope_set_view(void *p,const H *rect){
    if(p!=delegate)bad=1;
    for(U i=0;i<4;i++)queue_viewport[i]=rect[i];
    scope_view_sets++;
}
static U scope_get_state(void *p,U index){
    if(p!=delegate||index>=13){bad=1;return 0;}
    return delegate[0x28/4+1+index];
}
static int scope_set_state(void *p,U index,U value){
    if(p!=delegate||(index!=7&&index!=8&&index!=2)||value)bad=1;
    simulated_graphics_state[index]=value;scope_state_sets++;return 1;
}
#ifdef NATIVE_RECT_MODULE_CONTRACT
#include "native_rect_module_contract.h"
#endif
static int rect_owned_scope_contract(U base){
    queue_dtable[0x44/4]=(U)scope_set_view;
    queue_dtable[0x48/4]=base+0x7eaefd;
    queue_dtable[0x5c/4]=base+0x7eaf2d;
    queue_dtable[0x24/4]=(U)scope_set_state;
    queue_dtable[0x28/4]=(U)scope_get_state;
    *(H *)((unsigned char *)delegate+0x14)=640;
    *(H *)((unsigned char *)delegate+0x16)=480;
    const H old_view[4]={11,13,600,440};
    /* Actual begin/end, both transform stacks, viewport wrappers, state
     * push/pop, and queue emission. Only buffer/GPU/state application mocked. */
    for(U scenario=0;scenario<7;scenario++){
        for(U i=0;i<0x84/4;i++)queue_state[i]=0;
        queue_state[1]=queue_state[2]=(U)queue_vbuffer;
        queue_state[3]=queue_state[4]=(U)queue_ibuffer;
        queue_state[5]=queue_state[6]=0x1234;queue_state[7]=(U)queue_shader;
        queue_state[0x44/4]=1;
        rect_context[0x348/4]=scenario%2;
        ((unsigned char *)rect_context)[0x404]=0;
        ((unsigned char *)delegate)[0xa4]=0;
        U mode=rect_context[0x348/4],nodes[2]={rect_stack(0)[4],rect_stack(1)[4]},saved_matrix[2][16];
        for(U k=0;k<2;k++)for(U i=0;i<16;i++)saved_matrix[k][i]=rect_matrix_data(rect_stack(k))[i];
        for(U i=0;i<13;i++)delegate[0x28/4+1+i]=simulated_graphics_state[i]=100+i;
        for(U i=0;i<4;i++)queue_viewport[i]=old_view[i];
        bad=restored=scope_view_sets=scope_state_sets=queue_draws=rect_state_calls=0;
        queue_gpu_result=1;queue_stage=1;rect_state_guard=2;rect_bar_percent=42;
        rect_bar_failure=scenario>=2?scenario-1:0;
        rect_vtable[0x7c/4]=scenario>=2?(U)rect_state_emit:base+0x7ecf9d;
        int rc=native_rect_bar_owned(base,rect_context,42);
        if(rc!=(scenario>=2?-2:0)||bad||restored!=13||scope_view_sets!=2||scope_state_sets!=3||
           ((unsigned char *)rect_context)[0x404]||((unsigned char *)delegate)[0xa4]||
           rect_context[0x348/4]!=mode||queue_draws!=(scenario>=2?0U:1U))return 1;
        for(U i=0;i<4;i++)if(queue_viewport[i]!=old_view[i])return 2;
        for(U k=0;k<2;k++){
            if(rect_stack(k)[4]!=nodes[k])return 3;
            for(U i=0;i<16;i++)if(rect_matrix_data(rect_stack(k))[i]!=saved_matrix[k][i])return 4;
        }
        for(U i=0;i<13;i++)if(simulated_graphics_state[i]!=100+i)return 5;
    }
    U changes=scope_view_sets;
    ((unsigned char *)rect_context)[0x404]=1;
    if(native_rect_bar_owned(base,rect_context,42)!=-1)return 6;
    ((unsigned char *)rect_context)[0x404]=0;((unsigned char *)delegate)[0xa4]=1;
    if(native_rect_bar_owned(base,rect_context,42)!=-1)return 7;
    ((unsigned char *)delegate)[0xa4]=0;*(H *)((unsigned char *)rect_context+0x326)=1;
    if(native_rect_bar_owned(base,rect_context,42)!=-1||scope_view_sets!=changes)return 8;
    *(H *)((unsigned char *)rect_context+0x326)=0;
    printf("NATIVE_RECT_OWNED_SCOPE_OK frames=7 native_begin_end=1 viewport_restored=1 matrices_restored=1 state_restored=1 failure_cleanup=1 nesting_rejected=1 gpu_simulated=1\n");
#ifdef NATIVE_RECT_MODULE_CONTRACT
    if(rect_module_contract(base))return 9;
#endif
    return 0;
}

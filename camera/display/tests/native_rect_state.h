/* Offline only: actual native rectangle enter/leave and transform stacks.
 * Only final rectangle emission, state application and flush are intercepted.
 * This does not install a callback or exercise a camera/GPU. */
static U rect_context[0x408/4],rect_vtable[80],rect_matrix[2][16];
static U rect_state_calls,rect_state_flushes,rect_state_guard,rect_state_result;
static U rect_bar_base,rect_bar_percent,rect_bar_failure;
static int rect_bar_rc;
#ifdef NATIVE_RECT_SERVICE_CONTRACT
static U queue_service_alignment;
#endif
#define A7C_RECT_BAR_OFFLINE
#include "../module/native_rect_bar.h"
static unsigned char *rect_shared_color;
static void (*rect_set_color)(const unsigned char *);
static U *(*rect_matrix_data)(void *);
static U *rect_state_context(void){return rect_context;}
static U *rect_stack(U index){return rect_context+(0x34c+index*0x5c)/4;}
static int rect_state_emit(void *context,const unsigned char *color,const H *area){
    if(context!=rect_context||rect_context[0x348/4]!=0||rect_state_calls>=5)bad=1;
    for(U i=0;i<4;i++){
        U expected=rect_state_calls<5?rects[rect_state_calls][i]:0;
        if(rect_state_guard==2&&rect_state_calls==4&&i==2)expected=rect_bar_percent*16/100*4-2;
#ifdef NATIVE_RECT_SERVICE_CONTRACT
        if(queue_service_alignment&&i==0)expected-=552;
        if(queue_service_alignment&&i==1)expected+=5;
#endif
        if(color[i]!=255||area[i]!=expected)bad=1;
    }
    /* With zero native offset/rotation and 640x480 the draw matrix is identity,
     * even though the pre-existing matrix below deliberately is not. */
    U *matrix=rect_matrix_data(rect_stack(0));
    for(U i=0;i<16;i++)if(matrix[i]!=(i%5==0?0x3f800000U:0))bad=1;
    if(!((unsigned char *)(delegate+0x28/4))[0x7c])bad=1;
    rect_state_calls++;
    if(rect_state_guard==2){
        /* Simulate changed final GPU state, not a mutation of Sony's CPU
         * bookkeeping; the original pop must request all 13 original values. */
        for(U i=0;i<13;i++)simulated_graphics_state[i]=1000+i;
        return rect_state_calls!=rect_bar_failure;
    }
    return (int)rect_state_result;
}
static void rect_state_flush(void *context){
    if(context!=rect_context||restored!=13||
       ((unsigned char *)(delegate+0x28/4))[0x7c])bad=1;
    rect_state_flushes++;
}
static void rect_state_callback(void){
    if(rect_state_guard==2){rect_bar_rc=native_rect_bar(rect_bar_base,rect_context,rect_bar_percent);return;}
    U mode=rect_context[0x348/4];unsigned char saved[4];
    for(U i=0;i<4;i++)saved[i]=rect_shared_color[i];
    rect_set_color(rect_color);
    for(U i=0;i<5;i++)rect_native(rects[i][0],rects[i][1],rects[i][2],rects[i][3]);
    /* Native leave restores the matrix, but not these two shared values. */
    if(rect_state_guard){
        rect_set_color(saved);
        ((void (*)(void *,U))rect_vtable[0xd0/4])(rect_context,mode);
    }
}
#include "native_rect_queue.h"
static int rect_state_contract(U base,void (*post)(void *)){
    if(replace(base+0x66dd9c,rect_state_context))return 1;
    rect_native=(void *)(base+0x672319);
    rect_set_color=(void *)(base+0x672301);
    rect_shared_color=(void *)(base+0x1453967);
    rect_matrix_data=(void *)(base+0x802b0f);
    void (*ctor)(void *)=(void *)(base+0x802977);
    void (*dtor)(void *)=(void *)(base+0x8028ed);
    for(U i=0;i<80;i++)rect_vtable[i]=((U *)(base+0x13b68c0))[i];
    rect_context[0]=(U)rect_vtable;rect_context[4]=(U)delegate;
    rect_vtable[0x7c/4]=(U)rect_state_emit;
    rect_vtable[0x1c/4]=(U)rect_state_flush;
    /* Actual wrapper/delegate push/pop already audited in this fixture. */
    delegate[0]=base+0x13b6648;
    U *state=delegate+0x28/4;state[0]=(U)state_vtable;
    state_vtable[2]=(U)restore_state;
    for(U k=0;k<2;k++){
        ctor(rect_stack(k));U *matrix=rect_matrix_data(rect_stack(k));
        for(U i=0;i<16;i++)matrix[i]=rect_matrix[k][i]=0x3f800000U+(k*16+i)*0x10000;
    }
    *(H *)(base+0x1453978)=640;*(H *)(base+0x1453964)=480;
    *(U *)(base+0x145396c)=0;*(U *)(base+0x1453970)=0;*(U *)(base+0x1453974)=0;
    unsigned char original[4]={17,34,51,68};
    native_set_callback(engine,(void *)rect_state_callback);native_set_enabled(engine,1);
    /* First prove the unguarded leak; then preserve it, including a backend
     * returning failure. Repeated frames must not grow the active stack. */
    for(U scenario=0;scenario<3;scenario++)for(U frame=0;frame<20;frame++){
        rect_state_guard=scenario!=0;rect_state_result=scenario!=2;
        rect_context[0x348/4]=1;rect_set_color(original);
        for(U i=0;i<13;i++)state[i+1]=100+i;
        bad=restored=rect_state_calls=rect_state_flushes=0;
        U nodes[2]={rect_stack(0)[4],rect_stack(1)[4]};
        post(engine);
        if(bad||rect_state_calls!=5||rect_state_flushes!=1||restored!=13)return 2;
        if(rect_context[0x348/4]!=(rect_state_guard?1U:0U))return 3;
        for(U i=0;i<4;i++)if(rect_shared_color[i]!=(rect_state_guard?original[i]:255))return 4;
        for(U k=0;k<2;k++){
            if(rect_stack(k)[4]!=nodes[k])return 5;
            U *matrix=rect_matrix_data(rect_stack(k));
            for(U i=0;i<16;i++)if(matrix[i]!=rect_matrix[k][i])return 6;
        }
    }
    rect_bar_base=base;rect_state_guard=2;
    ((unsigned char *)rect_context)[0x404]=1;
    /* Real native push/pop/identity/translation/rotation, repeated 0/42/99%,
     * plus failure at each rectangle. Failure must restore before flush. */
    for(U scenario=0;scenario<8;scenario++)for(U frame=0;frame<20;frame++){
        rect_bar_percent=scenario==0?0:scenario==1?42:99;
        rect_bar_failure=scenario<3?0:scenario-2;
        rect_context[0x348/4]=1;rect_set_color(original);
        for(U i=0;i<13;i++)state[i+1]=100+i;
        bad=restored=rect_state_calls=rect_state_flushes=0;
        U nodes[2]={rect_stack(0)[4],rect_stack(1)[4]};
        post(engine);
        U expected=rect_bar_failure?rect_bar_failure:rect_bar_percent?5:4;
        if(bad||rect_state_calls!=expected||rect_state_flushes!=1||restored!=13||
           rect_bar_rc!=(rect_bar_failure?-2:0)){
            printf("RECT_BAR_FAIL scenario=%u frame=%u bad=%u calls=%u flushes=%u restored=%u rc=%d\n",
                   scenario,frame,bad,rect_state_calls,rect_state_flushes,restored,rect_bar_rc);
            return 9;
        }
        if(rect_context[0x348/4]!=1)return 10;
        for(U i=0;i<13;i++)if(simulated_graphics_state[i]!=100+i)return 16;
        for(U i=0;i<4;i++)if(rect_shared_color[i]!=original[i])return 11;
        for(U k=0;k<2;k++){
            if(rect_stack(k)[4]!=nodes[k])return 12;
            U *matrix=rect_matrix_data(rect_stack(k));
            for(U i=0;i<16;i++)if(matrix[i]!=rect_matrix[k][i])return 13;
        }
    }
    rect_state_calls=0;
    if(native_rect_bar(base,rect_context,100)!=-1||rect_state_calls)return 14;
    ((unsigned char *)rect_context)[0x404]=0;
    if(native_rect_bar(base,rect_context,42)!=-1||rect_state_calls)return 15;
    ((unsigned char *)rect_context)[0x404]=1;rect_context[0x348/4]=2;
    if(native_rect_bar(base,rect_context,42)!=-1||rect_state_calls||rect_context[0x348/4]!=2)return 17;
    int queue_rc_=rect_queue_contract(base,post);
    if(queue_rc_){printf("NATIVE_RECT_QUEUE_FAIL %d bad=%u draws=%u vertices=%u indices=%u\n",queue_rc_,bad,queue_draws,queue_vertices_set,queue_indices_set);return 18;}
    native_set_enabled(engine,0);rect_state_calls=rect_state_flushes=restored=0;post(engine);
    if(rect_state_calls||rect_state_flushes||restored)return 7;
    for(U k=0;k<2;k++)dtor(rect_stack(k));
    if(replace(base+0x66dd9c,get_backend))return 8;
    printf("NATIVE_RECT_STATE_OK frames=60 native_transform_stack=1 matrix_restored=1 unguarded_mode_color_leak=1 guarded_restore=1 backend_failure_restore=1 backend_simulated=1\n");
    printf("NATIVE_RECT_BAR_OK frames=160 progress=0,42,99 fail_each_rectangle=1 local_color=1 single_scope=1 state_restored=1 invalid_rejected=1 backend_simulated=1\n");
    return 0;
}

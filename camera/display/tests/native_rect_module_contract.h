/* Actual rectangle DSO atop the existing real native queue/scope fixture.
 * Children isolate all modified tables and module state. GPU is simulated. */
#include "../module/event_state.h"
extern int fflush(void *),getpid(void);
#ifdef NATIVE_RECT_NO_IDLE_CONTRACT
#define TRIAL_IDLE_DRAWS 0U
#define TRIAL_IDLE_PERCENT 101U
#else
#define TRIAL_IDLE_DRAWS 1U
#define TRIAL_IDLE_PERCENT 100U
#endif
static U trial_forwarded,trial_base;
#ifdef NATIVE_RECT_SERIES_CONTRACT
static U trial_expected_slot;
#endif
static void trial_original(void){
    trial_forwarded++;
    if(*(U *)(trial_base+0x14539d8+0x5c)!=
#ifdef NATIVE_RECT_SERIES_CONTRACT
       trial_expected_slot||
#else
       trial_base+0x675279||
#endif
       ((unsigned char *)rect_context)[0x404]||((unsigned char *)delegate)[0xa4])bad=1;
}
static void trial_foreign(void){}
#ifdef NATIVE_RECT_LIFECYCLE_ACK_CONTRACT
static U lifecycle_message[5],lifecycle_inactive,lifecycle_active;
static int lifecycle_replace_plt(U address,void *callback){
    /* Sony's sender uses BLX into ARM PLT entries, not Thumb bodies. */
    U page=address&~4095U;
    if(mprotect((void *)page,4096,7))return 1;
    U *code=(void *)address;code[0]=0xe51ff004;code[1]=(U)callback;
    __clear_cache(code,code+2);
    return mprotect((void *)page,4096,5)!=0;
}
static int lifecycle_allocate(U queue,U **out,U bytes,int wait){
    if(queue!=0x94016a||bytes!=16||wait!=1)_exit(61);
    for(U i=0;i<5;i++)lifecycle_message[i]=0xdeadbeef;
    *out=lifecycle_message+1;return 0;
}
static int lifecycle_send(U queue,U *message){
    if(queue!=0x94016a||message!=lifecycle_message+1||message[-1]!=queue||
       message[1]!=2031||message[2]||message[3])_exit(62);
    if(message[0]==0x940122)lifecycle_inactive++;
    else if(message[0]==0x940123)lifecycle_active++;
    else _exit(63);
    return 0;
}
#endif
static int rect_module_contract(U base){
    for(U scenario=0;scenario<
#ifdef NATIVE_RECT_SERVICE_CONTRACT
    26
#elif defined(NATIVE_RECT_SERIES_CONTRACT)
    21
#else
    18
#endif
    ;scenario++){
        int child=fork();if(child<0)return 1;
        if(!child){
#ifdef NATIVE_RECT_LIFECYCLE_ACK_CONTRACT
            /* Execute the original Sony sender, mock only the OSAL boundary. */
            if(lifecycle_replace_plt(base+0x10dc98,lifecycle_allocate)||
               lifecycle_replace_plt(base+0x10f3b8,lifecycle_send))_exit(64);
#endif
#ifdef NATIVE_RECT_SERVICE_CONTRACT
            queue_service_alignment=1;
#endif
            U window[64]={0},surface[32]={0},vector[4]={0},bitmap[32]={0},desc[16]={0};
#ifdef NATIVE_RECT_SERVICE_CONTRACT
            U second_bitmap[32]={0},second_desc[16]={0};
#endif
            U *manager=(void *)(base+0x1453df0),*table=(void *)(base+0x14539d8);
            for(U i=0;i<0x84/4;i++)queue_state[i]=0;
            queue_state[1]=queue_state[2]=(U)queue_vbuffer;
            queue_state[3]=queue_state[4]=(U)queue_ibuffer;
            queue_state[5]=queue_state[6]=0x1234;queue_state[7]=(U)queue_shader;
            queue_state[0x44/4]=1;
            rect_vtable[0x7c/4]=base+0x7ecf9d;
            /* Preserve fixed vtable identity while substituting GPU bindings. */
            for(U k=0;k<2;k++){
                U addr=base+(k?0x13b6648:0x13b68c0),*src=k?queue_dtable:rect_vtable;
                if(mprotect((void *)(addr&~4095U),8192,3))_exit(2);
                for(U i=0;i<(k?64U:80U);i++)((U *)addr)[i]=src[i];
            }
            rect_context[0]=base+0x13b68c0;rect_context[4]=(U)delegate;
            delegate[0]=base+0x13b6648;
            *(U *)(base+0x1453918)=(U)rect_context;
            rect_context[0x348/4]=scenario%2;
            ((unsigned char *)rect_context)[0x404]=0;((unsigned char *)delegate)[0xa4]=0;
            for(U i=0;i<13;i++)delegate[0x28/4+1+i]=simulated_graphics_state[i]=100+i;
            const H view[4]={11,13,600,440};
            for(U i=0;i<4;i++)queue_viewport[i]=view[i];
            manager[0x58/4]=1;manager[0x8c/4]=(U)bitmap;
            delegate[0x164/4]=(U)window;delegate[0x16c/4]=(U)surface;
            window[0]=base+0x13b3da0;window[1]=0xcefacade;
            surface[0x6c/4]=(U)window;surface[2]=1;
            window[0xb0/4]=(U)vector;window[0xb4/4]=(U)vector+8;
            vector[0]=(U)bitmap;bitmap[0]=base+0x13b1f50;bitmap[1]=(U)desc;bitmap[2]=0x10000;
            desc[4]=desc[6]=0x01e00280;desc[7]=1;desc[9]=0xfe33a000;
            *(H *)(base+0x1453978)=640;*(H *)(base+0x1453964)=480;
            *(U *)(base+0x145396c)=*(U *)(base+0x1453970)=*(U *)(base+0x1453974)=0;
            *(unsigned char *)(base+0x13e5b61)=*(unsigned char *)(base+0x13e5b62)=100;
            bad=restored=scope_view_sets=scope_state_sets=queue_draws=rect_state_calls=0;
            queue_gpu_result=1;queue_stage=1;rect_state_guard=2;rect_bar_percent=42;
            rect_bar_failure=0;trial_forwarded=0;trial_base=base;
            int expected=0;
            if(scenario==2){manager[0x58/4]=2;expected=-10;}
            if(scenario==3){delegate[0]=0;expected=-11;}
            if(scenario==4){window[1]=0;expected=-12;}
            if(scenario==5){window[0xbc/4]=1;expected=-13;}
            if(scenario==6){desc[9]=0;expected=-14;}
            if(scenario==7){*(unsigned char *)(base+0x13e5b61)=99;expected=-15;}
            if(scenario==8){*(U *)(base+0x1453974)=1;expected=-15;}
            if(scenario==9){*(H *)(base+0x1453978)=720;expected=-15;}
            if(scenario==10){rect_context[0x348/4]=2;expected=-1;}
            if(scenario==11){((unsigned char *)rect_context)[0x340]=1;expected=-1;}
            if(scenario==12){*(H *)((unsigned char *)rect_context+0x326)=1;expected=-1;}
            if(scenario==13){*(U *)(base+0x1453918)=0;expected=-10;}
            if(scenario==17){
                ((U *)(base+0x13b68c0))[0x7c/4]=(U)rect_state_emit;
                rect_bar_failure=3;expected=-2;
            }
#ifdef NATIVE_RECT_SERVICE_CONTRACT
            if(scenario>=18
#ifdef NATIVE_RECT_SINGLE_BUFFER_CONTRACT
               &&scenario<25
#endif
               ){
                window[0xb4/4]=(U)vector+16;window[0xbc/4]=scenario==19?1:0;
                vector[1]=vector[3]=2;vector[2]=(U)second_bitmap;
                for(U i=0;i<32;i++)second_bitmap[i]=bitmap[i];
                for(U i=0;i<16;i++)second_desc[i]=desc[i];
                second_bitmap[1]=(U)second_desc;
                desc[9]=0x22ab2000;second_desc[9]=0x22b48000;
                if(scenario==20){window[0xbc/4]=2;expected=-13;}
                if(scenario==21){manager[0x8c/4]=0x10000;expected=-13;}
                if(scenario==22){vector[3]=3;expected=-13;}
                if(scenario==23){desc[7]=2;expected=-14;}
                if(scenario==24){desc[9]++;expected=-14;}
#ifdef NATIVE_RECT_SINGLE_BUFFER_CONTRACT
                expected=-13;
#endif
            }
#endif
            *(U *)(base+0x1453914)=(U)table;table[0x5c/4]=base+0x675279;
            void *module=dlopen("/trial/marker.so",2);if(!module)_exit(3);
            int (*init)(void)=dlsym(module,"IM_SAMPLE_SO_init"),(*finish)(void)=dlsym(module,"IM_SAMPLE_SO_exit");
            struct event_marker *m=dlsym(module,"a7c_native_marker");
            if(!init||!finish||!m||m->version!=
#ifdef NATIVE_RECT_SERVICE_CONTRACT
            21
#elif defined(NATIVE_RECT_UPLOAD_CONTRACT)
            18
#elif defined(NATIVE_RECT_SERIES_CONTRACT)
            17
#else
            16
#endif
            ||init())_exit(4);
            void (*fetched)(void)=(void *)table[0x5c/4];
#ifdef NATIVE_RECT_SERIES_CONTRACT
            trial_expected_slot=(U)fetched;
            #ifndef NATIVE_RECT_SERVICE_CONTRACT
            if(expected)trial_expected_slot=base+0x675279;
#endif
            rect_bar_percent=queue_expected_percent=20;
#ifdef NATIVE_RECT_UPLOAD_CONTRACT
            U *mailbox=(void *)((unsigned char *)m+sizeof *m+32);*mailbox=256+128+20;
#ifdef NATIVE_RECT_SERVICE_CONTRACT
            mailbox[1]=(U)getpid();
#endif
#endif
#endif
            if(replace(base+0x675278,trial_original))_exit(5);
#ifdef NATIVE_RECT_SERVICE_CONTRACT
            if(scenario==0){
                /* Native queue counter, not a mock of the service policy:
                 * actual DSO runs 1000 idle redraws before any upload. */
                U *idle_detail=(void *)((unsigned char *)m+sizeof *m);
                *mailbox=0;queue_expected_percent=rect_bar_percent=100;
                for(U idle=0;idle<1000;idle++){
                    restored=rect_state_calls=0;fetched();
                    if(bad||queue_draws!=(idle+1)*TRIAL_IDLE_DRAWS){
                        printf("IDLE_ABLATION_FAIL frame=%u bad=%u draws=%u rc=%d views=%u states=%u restored=%u voff=%u ioff=%u\n",idle,bad,queue_draws,m->capture_rc,scope_view_sets,scope_state_sets,restored,queue_vertex_offset,queue_index_offset);fflush(0);_exit(61);
                    }
                }
                if(trial_forwarded!=1000||idle_detail[3]!=1000*TRIAL_IDLE_DRAWS||
                   idle_detail[5]!=TRIAL_IDLE_PERCENT)_exit(62);
                if(scope_view_sets!=2000*TRIAL_IDLE_DRAWS||
                   scope_state_sets!=3000*TRIAL_IDLE_DRAWS)_exit(63);
                printf("IDLE_ABLATION frames=1000 native_submits=%u original_forwards=%u\n",queue_draws,trial_forwarded);fflush(0);
                mailbox[2]=2;queue_expected_percent=rect_bar_percent=102;
                restored=rect_state_calls=0;fetched();
                if(bad||idle_detail[5]!=(TRIAL_IDLE_DRAWS?102U:101U)||
                   queue_draws!=1001*TRIAL_IDLE_DRAWS){
                    printf("FTP_MARK_FAIL bad=%u percent=%u draws=%u rc=%d health=%u\n",bad,idle_detail[5],queue_draws,(int)idle_detail[2],mailbox[2]);fflush(0);_exit(64);
                }
                mailbox[2]=1;queue_expected_percent=rect_bar_percent=100;
                restored=rect_state_calls=0;fetched();
                if(bad||idle_detail[5]!=TRIAL_IDLE_PERCENT||
                   queue_draws!=1002*TRIAL_IDLE_DRAWS)_exit(65);
                printf("NATIVE_FTP_MARK_OK error=102 recovered=100\n");fflush(0);
                /* Restore counters for the unchanged transfer sequence below. */
                queue_draws=trial_forwarded=scope_view_sets=scope_state_sets=restored=rect_state_calls=0;
                idle_detail[3]=idle_detail[4]=0;m->captured=0;
                *mailbox=256|128|20;queue_expected_percent=rect_bar_percent=20;
            }
#endif
            if(scenario==14||scenario==15){
                if(scenario==15)table[0x5c/4]=(U)trial_foreign;
                int rc=finish();
                if(rc!=(scenario==15?-2:0))_exit(6);
                /* Foreign replacement is preserved; original still forwards. */
                fetched();
                if(m->captured||queue_draws||trial_forwarded!=1||
                   table[0x5c/4]!=(scenario==15?(U)trial_foreign:base+0x675279))_exit(7);
            }else{
                ((void (*)(void))(base+0x66de3d))();
                U *detail=(void *)((unsigned char *)m+sizeof *m);
                if(m->captured!=1||m->capture_rc!=
#ifdef NATIVE_RECT_SERVICE_CONTRACT
                   0||
#else
                   expected||
#endif
                   (int)detail[2]!=expected||
                   !m->tid||table[0x5c/4]!=
#ifdef NATIVE_RECT_SERIES_CONTRACT
                   trial_expected_slot||
#else
                   base+0x675279||
#endif
                   trial_forwarded!=1||bad)_exit(8);
                if(queue_draws!=(expected?0U:1U))_exit(9);
                if(!expected||scenario==17){
                    if(scope_view_sets!=2||scope_state_sets!=3||restored!=13||
                       rect_context[0x348/4]!=scenario%2)_exit(10);
                    for(U i=0;i<4;i++)if(queue_viewport[i]!=view[i])_exit(11);
                }else if(scope_view_sets||scope_state_sets||restored)_exit(12);
#ifdef NATIVE_RECT_SERVICE_CONTRACT
                if(scenario==25){
                    int (*suspend)(void)=dlsym(module,"IM_SAMPLE_SO_sus");
                    int (*resume)(void)=dlsym(module,"IM_SAMPLE_SO_res");
                    int (*inactive)(void)=dlsym(module,"IM_SAMPLE_SO_inact");
                    int (*active)(void)=dlsym(module,"IM_SAMPLE_SO_act");
                    if(!suspend||!resume||!inactive||!active)_exit(50);
                    /* Both reasons must clear, in either notification order.
                     * A fetched wrapper must still forward Sony's callback. */
                    for(U cycle=0;cycle<2;cycle++){
                        U draws=queue_draws,frames=detail[3],forwards=trial_forwarded;
                        if((cycle?inactive():suspend()) || (cycle?suspend():inactive()))_exit(51);
                        fetched();
                        if(queue_draws!=draws||detail[3]!=frames||trial_forwarded!=forwards+1||bad)_exit(52);
                        if(cycle?active():resume())_exit(53);
                        fetched();
                        if(queue_draws!=draws||detail[3]!=frames||trial_forwarded!=forwards+2||bad)_exit(54);
                        if(cycle?resume():active())_exit(55);
                        restored=rect_state_calls=0;fetched();
                        if(queue_draws!=draws+1||detail[3]!=frames+1||trial_forwarded!=forwards+3||bad)_exit(56);
                    }
                    if(m->suspend!=2||m->resume!=2||m->inactive!=2||m->active!=2)_exit(57);
#ifdef NATIVE_RECT_LIFECYCLE_ACK_CONTRACT
                    if(lifecycle_inactive!=2||lifecycle_active!=2)_exit(65);
#endif
                    U draws=queue_draws;
                    if(suspend()||inactive())_exit(58);
                    trial_expected_slot=base+0x675279;
                    if(finish()||resume()||active())_exit(59);
                    fetched();
                    if(queue_draws!=draws||table[0x5c/4]!=base+0x675279||bad)_exit(60);
#ifdef NATIVE_RECT_LIFECYCLE_ACK_CONTRACT
                    if(lifecycle_inactive!=3||lifecycle_active!=3)_exit(66);
                    printf("NATIVE_IM_ACK_OK inactive=3 active=3 body=2031 sus_res_no_message=1\n");
#endif
                    printf("NATIVE_RECT_LIFECYCLE_OK both_orders=1 paused_forward_only=1 stopped_not_rearmed=1\n");
                    fflush(0);_exit(0);
                }
#endif
#ifdef NATIVE_RECT_SERIES_CONTRACT
                if(!expected){
                    if(detail[3]!=1||detail[4]!=1||detail[5]!=20||detail[6])_exit(14);
#ifndef NATIVE_RECT_SERVICE_CONTRACT
                    if(scenario>=18){
                        U other[32];for(U i=0;i<32;i++)other[i]=bitmap[i];
                        if(scenario==18){vector[0]=manager[0x8c/4]=(U)other;}
                        if(scenario==19)m->tid++;
                        if(scenario==20){
#ifdef NATIVE_RECT_UPLOAD_CONTRACT
                            *mailbox=0;
#else
                            detail[3]=1200;
#endif
                        }
                        trial_expected_slot=base+0x675279;fetched();
                        int stopped_rc=scenario==18?-16:scenario==19?-20:0;
                        if(m->capture_rc!=stopped_rc||detail[6]!=(scenario==20?1U:2U)||
                           queue_draws!=1||table[0x5c/4]!=base+0x675279||bad||finish())_exit(20);
                        fetched();if(queue_draws!=1||trial_forwarded!=3||bad)_exit(21);
                        _exit(0);
                    }
#endif
                    for(U step=0;step<2;step++){
#ifdef NATIVE_RECT_SERVICE_CONTRACT
                        if(scenario==18||scenario==19)window[0xbc/4]=step;
#endif
                        /* Shift only trial time in this isolated fixture, no waits. */
                        #ifdef NATIVE_RECT_UPLOAD_CONTRACT
                        *mailbox=((step+2)<<8)|128|(step?80:42);
#else
                        detail[7]=m->sec*1000+m->nsec/1000000-(step?6500:3500);
#endif
                        rect_bar_percent=queue_expected_percent=step?80:42;restored=rect_state_calls=0;fetched();
                        if(bad||detail[3]!=step+2||detail[4]!=step+2||detail[5]!=rect_bar_percent||detail[6]){printf("SERIES_FAIL step=%u bad=%u frames=%u changes=%u percent=%u stop=%u rc=%d draws=%u\n",step,bad,detail[3],detail[4],detail[5],detail[6],m->capture_rc,queue_draws);fflush(0);_exit(15);}
                    }
                    #ifdef NATIVE_RECT_UPLOAD_CONTRACT
                    *mailbox=0;
#else
                    detail[7]=m->sec*1000+m->nsec/1000000-9500;
#endif
#ifdef NATIVE_RECT_SERVICE_CONTRACT
                    queue_expected_percent=rect_bar_percent=100;restored=rect_state_calls=0;fetched();
                    if(detail[5]!=TRIAL_IDLE_PERCENT||detail[6]||queue_draws!=3+TRIAL_IDLE_DRAWS||bad)_exit(16);
                    /* A second request begins at a lower percent after idle. */
                    *mailbox=1024|128|20;queue_expected_percent=rect_bar_percent=20;restored=rect_state_calls=0;fetched();
                    if(detail[5]!=20||detail[6]||queue_draws!=4+TRIAL_IDLE_DRAWS||bad)_exit(17);
                    trial_expected_slot=base+0x675279;
                    if(scenario==16){
                        trial_expected_slot=(U)fetched;
                        mailbox[1]=0;fetched();if(detail[6]||detail[5]!=101||queue_draws!=4+TRIAL_IDLE_DRAWS||bad)_exit(18);
                        mailbox[1]=(U)getpid();*mailbox=0;queue_expected_percent=rect_bar_percent=100;restored=rect_state_calls=0;fetched();
                        if(detail[5]!=TRIAL_IDLE_PERCENT||queue_draws!=4+2*TRIAL_IDLE_DRAWS||bad)_exit(22);
                        trial_expected_slot=base+0x675279;
                    }
                    if(finish()||m->restore_rc)_exit(19);
                    fetched();if(queue_draws!=4+(scenario==16?2U:1U)*TRIAL_IDLE_DRAWS||bad)_exit(20);
#else
                    trial_expected_slot=base+0x675279;fetched();
                    if(detail[6]!=1||queue_draws!=3||table[0x5c/4]!=base+0x675279||bad)_exit(16);
                    if(finish()||m->restore_rc)_exit(17);
                    fetched();if(queue_draws!=3||trial_forwarded!=5||bad)_exit(18);
#endif
                }else{
#ifdef NATIVE_RECT_SERVICE_CONTRACT
                    trial_expected_slot=base+0x675279;
                    if(finish()||m->restore_rc)_exit(19);
                    fetched();if(queue_draws||trial_forwarded!=2||bad)_exit(20);
#else
                    fetched();if(queue_draws||trial_forwarded!=2||finish()||m->restore_rc)_exit(19);
#endif
                }
#else
                fetched(); /* late fetched wrapper forwards without second draw */
                if(trial_forwarded!=2||queue_draws!=(expected?0U:1U)||finish()||m->restore_rc)_exit(13);
#endif
            }
            _exit(0);
        }
        int status=0;
        if(waitpid(child,&status,0)!=child||status){printf("RECT_MODULE_FAIL case=%u status=%d\n",scenario,status);return 20+scenario;}
        printf("RECT_MODULE_CASE scenario=%u ok=1\n",scenario);
    }
    printf(
#ifdef NATIVE_RECT_SERVICE_CONTRACT
    "NATIVE_RECT_SERVICE_OK 26"
#elif defined(NATIVE_RECT_SERIES_CONTRACT)
    "NATIVE_RECT_SERIES_OK 21"
#else
    "NATIVE_RECT_MODULE_OK 18"
#endif
    " actual_dso native_queue scope_restore cancellation stale_forward gpu_simulated\n");
    return 0;
}

/* Offline ARM only: real Sony indexed-draw preparation and dispatch.
 * Synthetic resource objects, texture preparation and GL calls; no GPU.
 * Run in a child so code-boundary substitutions cannot affect other tests. */
static U bd[100],bs[1],bv[1],bi[1],bl[1],bst[24],bvt[16],bit[16],blt[8],ba[12];
static U bcase,bgl,bbind,battr,benable,bcount,bfail;
static U bscissor_off,bscissor_on;
static void bdisable(U cap){if(cap!=0xc11)bfail=1;bscissor_off++;}
static void benable_cap(U cap){if(cap!=0xc11)bfail=1;bscissor_on++;}
static U bvalid(void *p){if(p!=bs)bfail=1;return bcase!=2;}
static U bprogram(void *p){if(p!=bs)bfail=1;return 7;}
static int btextures(void *p){if(p!=bd)bfail=1;return bcase!=5;}
static void bvertex(void *p,void *d){if(p!=bv||d!=bd)bfail=1;bbind++;}
static void bindex(void *p,void *d){if(p!=bi||d!=bd)bfail=1;bbind++;}
static U bstride(void *p){if(p!=bv)bfail=1;return 64;}
static U btype(void *p){if(p!=bi)bfail=1;return 1;}
static U bsize(void *p){if(p!=bi)bfail=1;return 28;}
static U blength(void *p){if(p!=bl)bfail=1;return 1;}
static void *battribute(void *p,U i){if(p!=bl||i)bfail=1;return ba;}
static int bloc(U program,void *name){if(program!=7||name!=ba)bfail=1;battr++;return bcase==8?-1:2;}
static void bpointer(U location,U n,U type,U norm,U stride,U offset){
    if(location!=2||n!=3||type!=0x1406||norm||stride!=64||offset)bfail=1;
}
static void benabled(U location){if(location!=2)bfail=1;benable++;}
static void bdraw(U mode,U count_,U type,U offset){
    if(mode!=5||count_!=28||type!=0x1403||offset)bfail=1;
    bgl++;bcount=count_;
}
static int rect_backend_child(U base){
    if(replace(base+0x7eb770,btextures)||replace(base+0x7bd160,bdraw)||
       replace(base+0x7bc1e0,bloc)||replace(base+0x7b81c0,bpointer)||
       replace(base+0x7bd040,benabled))return 1;
    bs[0]=(U)bst;bv[0]=(U)bvt;bi[0]=(U)bit;bl[0]=(U)blt;
    bst[0x40/4]=(U)bvalid;bst[0x4c/4]=(U)bprogram;
    bvt[0x28/4]=(U)bvertex;bvt[0x1c/4]=(U)bstride;
    bit[0x2c/4]=(U)bindex;bit[0x1c/4]=(U)btype;bit[0x18/4]=(U)bsize;
    blt[0x10/4]=(U)blength;blt[0xc/4]=(U)battribute;
    ba[0]=0x00736f70;ba[0x20/4]=3;ba[0x24/4]=0;ba[0x28/4]=0;
    int (*draw_)(void *,U,U,U)=(void *)(base+0x7ebacd);
    for(bcase=0;bcase<10;bcase++){
        for(U i=0;i<100;i++)bd[i]=0;
        bd[0x13c/4]=bcase==1?0:(U)bs;
        bd[0x118/4]=bcase==3?0:(U)bv;
        bd[0x130/4]=bcase==4?0:(U)bl;
        bd[0x124/4]=bcase==6?0:(U)bi;
        if(bcase==7||bcase==8)((unsigned char *)bd)[0x134]=1;
        bgl=bbind=battr=benable=bcount=bfail=0;
        int rc=draw_(bd,4,0,bcase==9?0:28);
        U succeeds=bcase==0||bcase>=7;
        if(rc!=(int)succeeds||bfail||bgl!=succeeds||
           (succeeds&&(bbind!=2||bcount!=28))||
           battr!=(bcase==7||bcase==8)||benable!=(bcase==7))return 10+bcase;
        if(succeeds&&(((unsigned char *)bd)[0x134]||((unsigned char *)bd)[0x140]))return 30+bcase;
    }
    if(replace(base+0x7bd340,bdisable)||replace(base+0x7bd0d0,benable_cap))return 40;
    U state[32]={0};state[3]=1;bfail=bscissor_off=bscissor_on=0;
    void (*set_state)(void *,U,U)=(void *)(base+0x7e35ed);
    set_state(state,2,0);
    if(state[3]||bscissor_off!=1||bscissor_on||bfail)return 41;
    set_state(state,2,1);
    if(state[3]!=1||bscissor_off!=1||bscissor_on!=1||bfail)return 42;
    return 0;
}
static int rect_backend_contract(U base){
    int pid=fork();if(pid<0)return 1;
    if(!pid)_exit(rect_backend_child(base));
    int status=0;if(waitpid(pid,&status,0)!=pid||status){
        printf("NATIVE_RECT_BACKEND_FAIL status=%d\n",status);return 2;
    }
    printf("NATIVE_RECT_BACKEND_OK cases=10 missing_resources_block=1 missing_attribute_still_success=1 count_fallback=1 native_prepare_dispatch=1 native_scissor_disable_restore=1 texture_and_gl_simulated=1\n");
    return 0;
}

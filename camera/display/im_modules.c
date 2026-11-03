/* ILCE-7C 2.00 read-only module inventory. No IPC, load/unload, ptrace,
 * writable file descriptors or process-memory writes. Host pins binary hashes. */
typedef unsigned U;
extern int open(const char *,int,...), close(int), read(int,void *,unsigned);
extern int pread(int,void *,unsigned,long), readlink(const char *,char *,unsigned);
extern int printf(const char *,...), snprintf(char *,unsigned,const char *,...);
extern int sscanf(const char *,const char *,...), strcmp(const char *,const char *);
extern int memcmp(const void *,const void *,unsigned);
extern unsigned long long strtoull(const char *,char **,int);
extern unsigned alarm(unsigned);
struct region { U lo,hi; };
static struct region regions[1024];
static U region_count, database_base;
#ifdef IM_NATIVE_PHASE
static U phase_mapping;
#endif
static int memory=-1;
static int rd(U a,void *out,U n) {
    if(!n || a<0x8000 || a>=0x80000000U || n>0x80000000U-a) return -1;
    for(U i=0;i<region_count;i++)
        if(a>=regions[i].lo && a+n<=regions[i].hi)
            return pread(memory,out,n,(long)a)==(int)n?0:-1;
    return -1;
}
static int get_maps(int pid) {
    char path[64], data[262144];
    snprintf(path,sizeof path,"/proc/%d/maps",pid);
    int fd=open(path,0); if(fd<0)return -1;
    unsigned count=0;
    for(;;) {
        if(count==sizeof data-1){printf("MAPS_ERROR byte_limit\n");close(fd);return -1;}
        int n=read(fd,data+count,sizeof data-1-count);
        if(n<0){close(fd);return -1;} if(!n)break;count+=(U)n;
    }
    close(fd); data[count]=0;
    char *line=data;
    while(*line) {
        char *end=line;while(*end && *end!='\n')end++;
        char next=*end;*end=0;
        U lo=0,hi=0,offset=0;char perm[5]={0},name[128]={0};
        int fields=sscanf(line,"%x-%x %4s %x %*s %*s %127s",&lo,&hi,perm,&offset,name);
        if(fields<4 || hi<=lo){printf("MAPS_ERROR parse fields=%d\n",fields);return -1;}
#ifdef IM_NATIVE_PHASE
        /* Native Appframework diagnostic RAM, observed in 2.00. Unlike
         * ordinary data this /dev/mem VMA is write-only in the target. */
        if(fields==5 && !strcmp(name,"/dev/mem") && offset==0x03103000 &&
           hi-lo==0x3000 && perm[1]=='w') {
            if(phase_mapping)return -1;
            phase_mapping=lo;
        }
#endif
        if(perm[0]=='r' && hi<=0x80000000U) {
            if(region_count==1024){printf("MAPS_ERROR region_limit\n");return -1;}
            regions[region_count++]=(struct region){lo,hi};
        }
        if(fields==5 && !strcmp(name,"/usr/lib/libIMDB.so") && offset==0) {
            if(database_base)return -1;
            database_base=lo;
        }
        if(!next)break;line=end+1;
    }
    printf("MAPS_READ bytes=%u regions=%u imdb=%08x\n",count,region_count,database_base);
    return database_base?0:-1;
}
int main(int argc,char **argv) {
    alarm(5);
    char *end=0,path[64],exe[128];
    if(argc!=2)return 64;
    unsigned long long parsed=strtoull(argv[1],&end,10);
    if(!end || *end || parsed<2 || parsed>4194304)return 64;
    int pid=(int)parsed;
    snprintf(path,sizeof path,"/proc/%d/exe",pid);
    int n=readlink(path,exe,sizeof exe-1);if(n<=0 || n==(int)sizeof exe-1)return 65;
    exe[n]=0;if(strcmp(exe,"/usr/bin/im.elf"))return 65;
    if(get_maps(pid))return 66;
    snprintf(path,sizeof path,"/proc/%d/mem",pid);
    memory=open(path,0);if(memory<0)return 67;
    U magic=0,mask=0,head=0,state=0,terminator=0;
    unsigned char prologue[8];
    static const unsigned char expected[8]={0x90,0xb5,0x85,0xb0,0x27,0x4b,0x02,0xaf};
    if(rd(0x8000,&magic,4)||magic!=0x464c457f ||
       rd(0x97ec,prologue,8)||memcmp(prologue,expected,8) ||
       rd(database_base,&magic,4)||magic!=0x464c457f ||
       rd(database_base+0x10600,&terminator,4)||terminator!=40 ||
       rd(0x154ec,&mask,4)||rd(0x15424,&state,4)||rd(0x15514,&head,4))return 68;
    printf("IM_MODULES_READONLY pid=%d mask=%08x state=%08x imdb=%08x\n",pid,mask,state,database_base);
    U visited[256],count=0,loaded[3]={0,0,0};
    while(head) {
        if(count==256)return 69;
        for(U i=0;i<count;i++)if(visited[i]==head)return 69;
        visited[count++]=head;
        U node[8],descriptor[11];
        if(rd(head,node,sizeof node)||rd(node[2],descriptor,sizeof descriptor))return 70;
        U id=descriptor[3]&65535;
        if(id==2030)loaded[0]++;if(id==2028)loaded[1]++;if(id==2031)loaded[2]++;
#ifdef IM_MODULES_SUMMARY
        if(id==2031)
#endif
        printf("LOADED id=%u type=%08x state=%u handle=%08x descriptor=%08x\n",
               id,descriptor[0],node[5],node[4],node[2]);
        head=node[0];
    }
    for(U i=0;i<3;i++) {
        U entry[11];U address=database_base+0x1057c+i*44;
        if(rd(address,entry,sizeof entry))return 71;
        if((entry[3]&65535)!=(i==0?2030U:i==1?2028U:2031U))return 71;
        printf("CANDIDATE id=%u loaded=%u phase=%08x targets=%08x type=%08x\n",
               entry[3]&65535,loaded[i],entry[1],entry[2],entry[0]);
    }
    U final_head=0;
    if(rd(0x15514,&final_head,4)||final_head!=(count?visited[0]:0))return 72;
    close(memory);
    printf("IM_MODULES_END count=%u head_unchanged=1 snapshot_not_locked=1\n",count);
    return 0;
}

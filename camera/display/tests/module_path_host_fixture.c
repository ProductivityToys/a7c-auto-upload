#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <poll.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include "../module/path_transaction.h"
static unsigned char *bytes;
static int budget=-1,read_fail;
static int read_bytes(unsigned char *out) {if(read_fail)return -1;memcpy(out,bytes,PATH_BYTES);return 0;}
static int write_bytes(unsigned off,const unsigned char *p,unsigned n) {
    if(budget==0)return -1;
    if(budget>0 && n>(unsigned)budget)n=(unsigned)budget;
    memcpy(bytes+off,p,n);if(budget>0)budget-=(int)n;return (int)n;
}
static struct path_transaction tx={"libIMSample.so","/tmp_bt/a7n.so",read_bytes,write_bytes};
int main(void) {
    bytes=mmap(0,4096,PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANON,-1,0);
    if(bytes==MAP_FAILED)return 1;
    for(int cut=0;cut<PATH_BYTES;cut++) {
        memcpy(bytes,tx.original,PATH_BYTES);budget=cut;
        if(path_install(&tx)!=3)return 2;
        budget=-1;if(path_restore(&tx)||memcmp(bytes,tx.original,PATH_BYTES))return 3;
    }
    memcpy(bytes,tx.original,PATH_BYTES);budget=-1;
    if(path_install(&tx)||memcmp(bytes,tx.replacement,PATH_BYTES))return 4;
    budget=7;if(path_restore(&tx)!=3)return 5;
    budget=-1;if(path_restore(&tx)||memcmp(bytes,tx.original,PATH_BYTES))return 6;
    bytes[0]='!';if(path_restore(&tx)!=2 || bytes[0]!='!')return 7;
    memcpy(bytes,tx.original,PATH_BYTES);read_fail=1;
    if(path_install(&tx)!=1 || memcmp(bytes,tx.original,PATH_BYTES))return 8;
    read_fail=0;
    /* Kill a writer after a partial install. Its child guardian must observe
       pipe EOF and restore through the same transaction core. */
    int result[2];if(pipe(result))return 9;
    pid_t parent=fork();if(parent<0)return 10;
    if(!parent) {
        close(result[0]);int control[2];if(pipe(control))_exit(11);
        pid_t guardian=fork();if(guardian<0)_exit(12);
        if(!guardian) {
            close(control[1]);struct pollfd p={control[0],POLLIN,0};
            int r=poll(&p,1,3000);budget=-1;
            int outcome=r>0?path_restore(&tx):-1;
            if(write(result[1],&outcome,sizeof outcome)!=(int)sizeof outcome)_exit(13);
            _exit(outcome?14:0);
        }
        close(control[0]);close(result[1]);
        budget=7;path_install(&tx);kill(getpid(),SIGKILL);_exit(15);
    }
    close(result[1]);int st=0;waitpid(parent,&st,0);
    struct pollfd ready={result[0],POLLIN,0};int outcome=-1;
    if(!WIFSIGNALED(st)||WTERMSIG(st)!=SIGKILL||poll(&ready,1,4000)<=0||
       read(result[0],&outcome,sizeof outcome)!=(int)sizeof outcome||outcome||
       memcmp(bytes,tx.original,PATH_BYTES))return 16;
    close(result[0]);munmap(bytes,4096);
    puts("MODULE_PATH_OK partial_install=15 partial_restore=1 conflict=1 read_failure=1 killed_parent=1");
    return 0;
}

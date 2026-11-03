/* No real device access: verify exact aperture and read-only mmap contract. */
#include <assert.h>
#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <string.h>
static unsigned char source[614400],output[614400];
static int opens,maps_count,unmaps,closes,failure;
static int fake_open(const char *path,int flags){
 assert(!strcmp(path,"/dev/mem")&&flags==O_RDONLY);opens++;
 if(failure==1){errno=13;return -1;}return 71;
}
static void *fake_mmap(void *addr,size_t n,int prot,int flags,int fd,off_t offset){
 assert(!addr&&n==sizeof source&&prot==PROT_READ&&flags==MAP_SHARED&&fd==71);
 assert(offset==0xfe33a000LL);maps_count++;
 if(failure==2){errno=22;return MAP_FAILED;}return source;
}
static int fake_munmap(void *p,size_t n){
 assert(p==source&&n==sizeof source);unmaps++;
 if(failure==3){errno=22;return -1;}return 0;
}
static int fake_close(int fd){assert(fd==71);closes++;return failure==4?-1:0;}
#define open fake_open
#define mmap fake_mmap
#define munmap fake_munmap
#define close fake_close
#include "../capture_physical.h"
int main(void){
 assert(capture_physical_read(0xfe33b000,sizeof output,output)==84);
 assert(capture_physical_read(0xfe33a000,sizeof output-1,output)==84);
 assert(capture_physical_read(0xfe33a000,sizeof output,0)==84);
 assert(!opens&&!maps_count&&!unmaps&&!closes);
 for(unsigned i=0;i<sizeof source;i++)source[i]=(unsigned char)(i*13);
 assert(capture_physical_read(0xfe33a000,sizeof output,output)==0);
 assert(!memcmp(source,output,sizeof source));
 assert(opens==1&&maps_count==1&&unmaps==1&&closes==1);
 for(failure=1;failure<=4;failure++){
  opens=maps_count=unmaps=closes=0;
  assert(capture_physical_read(0xfe33a000,sizeof output,output)==84);
  assert(opens==1&&maps_count==(failure!=1)&&unmaps==(failure>=3)&&closes==(failure!=1));
 }
 puts("PASS: fixed aperture refusal, read-only mapping/copy, open/map/unmap/close failure cleanup");
 return 0;
}

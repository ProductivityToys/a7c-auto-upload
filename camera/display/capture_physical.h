/* ILCE-7C 2.00 single observed OSD aperture. Called only after validating
 * the native bitmap descriptor and existing /dev/mem VMA, and only by the
 * explicit read-only physical capture command. No writable mapping. */
#ifdef __arm__
extern void *mmap64(void *,unsigned,int,int,int,long long);
extern int munmap(void *,unsigned);
#define CAPTURE_MMAP mmap64
#define CAPTURE_PROT_READ 1
#define CAPTURE_MAP_SHARED 1
#else
#include <sys/mman.h>
#define CAPTURE_MMAP mmap
#define CAPTURE_PROT_READ PROT_READ
#define CAPTURE_MAP_SHARED MAP_SHARED
#endif
static int capture_physical_read(unsigned offset,unsigned bytes,unsigned char *out){
 if(offset!=0xfe33a000U||bytes!=614400U||!out)return 84;
 int fd=open("/dev/mem",O_RDONLY);
 if(fd<0){printf("DDS_PHYSICAL open_failed errno=%d\n",errno);return 84;}
 void *mapped=CAPTURE_MMAP(0,bytes,CAPTURE_PROT_READ,CAPTURE_MAP_SHARED,fd,
                          (long long)offset);
 if(mapped==(void *)-1){
  int e=errno;close(fd);printf("DDS_PHYSICAL mmap_failed errno=%d\n",e);return 84;
 }
 /* The destination is our RAM array. Volatile reads avoid speculative vector
  * loads beyond the verified aperture; do not flush or modify device memory. */
 const volatile unsigned char *p=mapped;
 for(unsigned i=0;i<bytes;i++)out[i]=p[i];
 int ur=munmap(mapped,bytes);int e=ur?errno:0;int cr=close(fd);
 printf("DDS_PHYSICAL copied=%u unmap=%d close=%d errno=%d\n",bytes,ur,cr,e);
 return ur||cr?84:0;
}

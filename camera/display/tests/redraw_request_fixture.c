/* Host-only fault injection: prove refusal paths cannot write native memory. */
#define pread mock_pread
#define pwrite mock_pwrite
#define main probe_main
#include "../redraw_once.c"
#undef main
#include <assert.h>
static unsigned writes;
static int bad_table,bad_callback,bad_code,read_error,write_error;
static unsigned char countdown;
ssize_t mock_pread(int unused,void *out,size_t n,off_t off){
 (void)unused;if(read_error)return -1;
 u32 v=0,cb[6]={0,0,0,0x674db9U,0x674a95U,0x674aadU};
 unsigned char code[16]={4,0x4b,0x80,0xb5,0x7b,0x44,0,0xaf,0x18,0x78,0,0x38,0x18,0xbf,1,0x20};
 if(off==base && n==4)v=0x464c457f;
 else if(off==base+0x1453914U && n==4)v=base+CALLBACKS+(bad_table?4:0);
 else if(off==base+CALLBACKS && n==sizeof cb){
  for(unsigned i=0;i<6;i++)cb[i]+=base;
  if(bad_callback)cb[4]^=4;
  memcpy(out,cb,n);return (ssize_t)n;
 }else if((off==base+0x674a94U||off==base+0x674aacU)&&n==16){
  if(off==base+0x674aacU){unsigned char tail[8]={0x1a,0x78,0x0a,0xb1,1,0x3a,0x1a,0x70};memcpy(code+8,tail,8);}
  if(bad_code)code[2]^=4;memcpy(out,code,16);return 16;
 }else if(off==base+COUNTER && n==1){*(unsigned char*)out=countdown;return 1;}
 else return -1;
 memcpy(out,&v,n);return (ssize_t)n;
}
ssize_t mock_pwrite(int unused,const void *p,size_t n,off_t off){
 (void)unused;assert(n==1 && off==base+COUNTER && *(const unsigned char*)p==2);
 writes++;if(write_error)return -1;countdown=2;return 1;
}
static void reset(void){base=0x06015000;fd=1;countdown=0;writes=0;bad_table=bad_callback=bad_code=read_error=write_error=0;}
int main(void){
 reset();assert(request()==0 && writes==1 && countdown==2);
 reset();countdown=1;assert(request()==66 && !writes && countdown==1);
 reset();countdown=2;assert(request()==66 && !writes && countdown==2);
 reset();bad_table=1;assert(request()==66 && !writes);
 reset();bad_callback=1;assert(request()==66 && !writes);
 reset();bad_code=1;assert(request()==66 && !writes);
 reset();read_error=1;assert(request()==66 && !writes);
 reset();write_error=1;assert(request()==67 && writes==1 && !countdown);
 puts("PASS: 8 redraw request/refusal cases");return 0;
}

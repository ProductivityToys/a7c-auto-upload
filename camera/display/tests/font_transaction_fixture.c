/* Host-only exhaustive cut-point recovery. No camera access. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../font_transaction.h"
static unsigned char live[FONT_BYTES];
static int budget,read_error,corrupt_after,write_calls;
static int rd(void *context,unsigned char *out){
 (void)context;if(read_error)return -1;
 memcpy(out,live,FONT_BYTES);return 0;
}
static int wr(void *context,unsigned off,const unsigned char *data,unsigned n){
 (void)context;assert(off<FONT_BYTES && n<=FONT_BYTES-off);write_calls++;
 if(budget<=0)return -1;
 if(n>(unsigned)budget)n=(unsigned)budget;
 memcpy(live+off,data,n);budget-=(int)n;
 if(corrupt_after)live[0]=0x55;
 return (int)n;
}
static struct font_transaction reset(void){
 struct font_transaction t={.read=rd,.write=wr};
 for(unsigned i=0;i<FONT_BYTES;i++){t.original[i]=(unsigned char)i;t.replacement[i]=(unsigned char)(255-i);}
 memcpy(live,t.original,FONT_BYTES);budget=FONT_BYTES;read_error=corrupt_after=write_calls=0;
 return t;
}
int main(void){
 unsigned cuts=0;
 for(int install_cut=0;install_cut<=FONT_BYTES;install_cut++){
  for(int restore_cut=0;restore_cut<=FONT_BYTES;restore_cut++){
   struct font_transaction t=reset();budget=install_cut;
   int ir=font_install(&t);assert(ir==(install_cut==FONT_BYTES?FONT_OK:FONT_WRITE));
   budget=restore_cut;int rr=font_restore(&t);
   assert(rr==FONT_OK||rr==FONT_WRITE);
   /* Independent guardian has the immutable originals, not a dirty flag. */
   struct font_transaction guardian=t;budget=FONT_BYTES;
   assert(font_restore(&guardian)==FONT_OK && !memcmp(live,t.original,FONT_BYTES));
   int previous=write_calls;assert(font_restore(&guardian)==FONT_OK && write_calls==previous);
   cuts++;
  }
 }
 struct font_transaction t=reset();live[7]=0x55;
 assert(font_install(&t)==FONT_CHANGED && !write_calls);
 assert(font_restore(&t)==FONT_CHANGED && !write_calls);
 t=reset();read_error=1;assert(font_install(&t)==FONT_READ && !write_calls);
 assert(font_restore(&t)==FONT_READ && !write_calls);
 t=reset();corrupt_after=1;assert(font_install(&t)==FONT_VERIFY);
 corrupt_after=0;budget=FONT_BYTES;int previous=write_calls;
 assert(font_restore(&t)==FONT_CHANGED && write_calls==previous);
 printf("PASS: %u install/restore cut-point pairs; conflict, read failure, corrupt readback, idempotence\n",cuts);
 return 0;
}

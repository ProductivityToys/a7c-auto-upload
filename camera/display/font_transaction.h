/* Bounded font replacement/recovery core. No addresses, camera I/O or fonts.
 * The adapter must pin the verified target process and enforce native slot
 * checks. Prepare original/replacement in the guardian BEFORE any write.
 * A failed/partial write is recoverable from current bytes, not a parent flag.
 */
#ifndef A7C_FONT_TRANSACTION_H
#define A7C_FONT_TRANSACTION_H
#define FONT_BYTES 128
enum { FONT_OK=0, FONT_READ=1, FONT_CHANGED=2, FONT_WRITE=3, FONT_VERIFY=4 };
struct font_transaction {
 unsigned char original[FONT_BYTES],replacement[FONT_BYTES];
 void *context;
 int (*read)(void *,unsigned char *); /* Exactly 128 bytes, zero on success. */
 int (*write)(void *,unsigned,const unsigned char *,unsigned); /* count or <0 */
};
static int font_equal(const unsigned char *a,const unsigned char *b){
 for(unsigned i=0;i<FONT_BYTES;i++)if(a[i]!=b[i])return 0;
 return 1;
}
static int font_write_all(struct font_transaction *t,const unsigned char *target){
 unsigned off=0;
 while(off<FONT_BYTES){
  int n=t->write(t->context,off,target+off,FONT_BYTES-off);
  if(n<=0||(unsigned)n>FONT_BYTES-off)return FONT_WRITE;
  off+=(unsigned)n;
 }
 unsigned char now[FONT_BYTES];
 if(t->read(t->context,now))return FONT_READ;
 return font_equal(now,target)?FONT_OK:FONT_VERIFY;
}
static int font_install(struct font_transaction *t){
 unsigned char now[FONT_BYTES];
 if(t->read(t->context,now))return FONT_READ;
 if(!font_equal(now,t->original))return FONT_CHANGED;
 return font_write_all(t,t->replacement);
}
static int font_restore(struct font_transaction *t){
 unsigned char now[FONT_BYTES];
 if(t->read(t->context,now))return FONT_READ;
 if(font_equal(now,t->original))return FONT_OK;
 /* A partial install OR restore can have an arbitrary prefix/suffix mix.
  * Foreign bytes are not ours to overwrite. This detects conflict, but does
  * not establish exclusive access against concurrent native readers/writers. */
 for(unsigned i=0;i<FONT_BYTES;i++)
  if(now[i]!=t->original[i]&&now[i]!=t->replacement[i])return FONT_CHANGED;
 return font_write_all(t,t->original);
}
#endif

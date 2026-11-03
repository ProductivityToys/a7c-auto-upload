/* Included only by the experimental text probe after DDS state helpers.
 * The build generates dds_text_asset.h from a hash-verified native image and
 * our fixed UPLOAD / TEST plan. Never trust a writable input font on-camera.
 */
#include "font_transaction.h"
#ifdef __arm__
extern int pwrite(int,const void *,unsigned,long);
#endif
#define FONT_ADDRESS 0x13eb2e0U
static int font_fd=-1,font_prepared;
#ifdef DDS_EDGE_EXPERIMENT
#include "dds_position_adapter.h"
#endif
static struct font_transaction font_tx;
static int font_read_native(void *context,unsigned char *out){
 (void)context;
 struct native_state s;
 if(snapshot(&s)||s.life[3]!=timer_id)return -1;
 return at(base+FONT_ADDRESS,out,FONT_BYTES);
}
static int font_write_native(void *context,unsigned offset,const unsigned char *p,unsigned n){
 (void)context;
 struct native_state s;
 if(snapshot(&s)||s.life[3]!=timer_id||offset>=FONT_BYTES||!n||n>FONT_BYTES-offset)return -1;
 return pwrite(font_fd,p,n,(long)(base+FONT_ADDRESS+offset));
}
static int experiment_prepare(void){
#ifdef DDS_EDGE_EXPERIMENT
 if(position_check())return 95;
#endif
 unsigned char code[8],font[FONT_BYTES];
 const unsigned char expected[8]={0x03,0xeb,0xcb,0x03,0x13,0xf8,0x05,0xa0};
 if(at(base+0x7db344U,code,8)||memcmp(code,expected,8)||
    at(base+FONT_ADDRESS,font,FONT_BYTES)||memcmp(font,original_font,FONT_BYTES))return 92;
 memcpy(font_tx.original,font,FONT_BYTES);
 memcpy(font_tx.replacement,replacement_font,FONT_BYTES);
 font_tx.read=font_read_native;font_tx.write=font_write_native;
 char path[64];snprintf(path,sizeof path,"/proc/%d/mem",native_pid);
 font_fd=open(path,2 /* O_RDWR */);if(font_fd<0)return 92;
 /* Both fork copies retain these originals before the first possible write. */
 font_prepared=1;return 0;
}
static int experiment_install(void){
 struct native_state s;
 if(!font_prepared||snapshot(&s)||s.life[3]!=timer_id||!other_slots_idle(&s)||
    s.slots[18]||s.slots[204])return 93;
 int r=font_install(&font_tx);
 printf("DDS_FONT install=%d\n",r);fflush(0);
 if(r)return 93;
#ifdef DDS_EDGE_EXPERIMENT
 r=position_change(0);
 printf("DDS_POSITION install=%d x=%u y=%u\n",r,half(position_target()),half(position_target()+2));fflush(0);
#endif
 return r;
}
static int experiment_restore(void){
 if(!font_prepared)return 0;
 /* Restore our shared data even if another DDS slot has become active. Never
  * clear that other slot or overwrite bytes foreign to original/replacement.
  * Slot inspection is conflict detection, not an exclusive native lock. */
 int r=font_restore(&font_tx);
 printf("DDS_FONT restore=%d\n",r);fflush(0);
#ifdef DDS_EDGE_EXPERIMENT
 /* Attempt both independent restorations even if one refuses. */
 int pr=position_change(1);
 printf("DDS_POSITION restore=%d x=30 y=250\n",pr);fflush(0);
 if(pr)return pr;
#endif
 return r?94:0;
}

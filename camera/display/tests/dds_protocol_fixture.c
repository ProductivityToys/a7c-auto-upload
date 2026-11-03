/* Host fault injection only; no real camera, ioctl or native message queue. */
#define pread fixture_pread
#define usleep fixture_usleep
#define main probe_main
#include "../dds_once.c"
#undef main
#include <assert.h>
static struct native_state live;
static u32 storage[4];
static unsigned types[32], sent, freed, cancelled, armed;
static int arm_fail;
static int alloc_fail, send_fail, cancel_fail, dropped, reactivate, sleeps, redraw_fail, redraw_calls;
static int fake_redraw(void){redraw_calls++;return redraw_fail;}
static int dumps,dump_fail;
static const char *expected_raw="shooting.raw";
static int fake_dump(const char *name,const void *buf,unsigned n){
 if(use_readonly_physical_capture){
  assert(!strcmp(name,expected_raw)&&buf==pixels&&n==614400);
 }else assert(!strcmp(name,"dds-before.rle")&&buf==packed&&n==28);
 dumps++;return dump_fail;
}
ssize_t fixture_pread(int fd,void *p,size_t n,off_t off){
 (void)fd;
 if(off==base && n==4){u32 magic=0x464c457f;memcpy(p,&magic,4);return 4;}
 if(off==base+LIFE && n==28){memcpy(p,live.life,n);return (ssize_t)n;}
 if(off==base+STATE && n==208){memcpy(p,live.slots,n);return (ssize_t)n;}
 return -1;
}
int fixture_usleep(useconds_t t){
 (void)t;sleeps++;
 if(reactivate && cancelled && sleeps==3)live.slots[204]=1;
 return 0;
}
int osal_valloc_msg_wait(u32 q,void *out,u32 size,int wait){
 assert(q==QUEUE && size==12 && wait==0);
 if(alloc_fail)return -1;
 *(u32**)out=storage+1;return 0;
}
int osal_free_msg(u32 q,void *m){assert(q==QUEUE && m==storage+1);freed++;return 0;}
int osal_snd_msg(u32 q,void *m){
 unsigned char *p=m;assert(q==QUEUE && ((u32*)m)[-1]==QUEUE);
 if(send_fail)return -1;
 unsigned type=p[0]|((unsigned)p[1]<<8);assert(sent<32);types[sent++]=type;
 if(dropped)return 0;
 live.life[4]=0;
 if(type==0x103){
  assert(p[2]==0 && p[3]==5 && !memcmp(p+4,marker,8));
  live.slots[18]=1;live.slots[20]=5;memcpy(live.slots+22,marker,8);live.slots[204]=1;
 }else if(type==0x104)live.slots[18]=0;
 else if(type==0xff02)live.slots[204]=live.slots[18];
 else assert(0);
 return 0;
}
int osal_snd_sync_direct(u32 q,void *payload){
 u32 *p=payload;assert(q==0x910040 && p[0]==48 && p[6]==239);
 if(p[4]==2){
  assert(p[8]==200000&&p[9]==0&&p[10]==2&&!p[7]&&!p[11]);
  armed++;p[5]=(u32)arm_fail;return 0;
 }
 assert(p[4]==3);
 assert(!p[1]&&!p[2]&&!p[3]);cancelled++;p[5]=(u32)cancel_fail;return 0;
}
static void reset(void){
 memset(&live,0,sizeof live);base=0x06015000;timer_id=239;memory_fd=1;
 live.life[0]=base+0x13b5238;live.life[2]=base+0x13b5288;
 live.life[3]=239;live.life[4]=1;live.life[5]=1;
 u32 vt=base+0x13b5270;memcpy(live.slots,&vt,4);
 sent=freed=cancelled=armed=0;arm_fail=0;alloc_fail=send_fail=cancel_fail=dropped=reactivate=sleeps=0;
 redraw_fail=redraw_calls=0;redraw_action=fake_redraw;
}
int main(void){
 reset();assert(arm_shooting_timer()==0&&!armed); /* lazy init owns first arm */
 live.life[4]=0;assert(arm_shooting_timer()==0&&armed==1);
 arm_fail=-1024;assert(arm_shooting_timer()==-1024&&armed==2);
 reset();live.life[4]=0;live.life[3]=240;assert(arm_shooting_timer()==70&&!armed);
 reset();live.life[4]=0;live.slots[18]=1;assert(arm_shooting_timer()==70&&!armed);
 reset();assert(message(0x103)==0 && sent==1 && freed==0);
 assert(cleanup()==0 && cancelled==1 && redraw_calls==1 && !live.slots[18] && !live.slots[204]);
 assert(types[1]==0x104 && types[2]==0xff02 && types[3]==0xff02);
 reset();send_fail=1;assert(message(0x103)!=0 && freed==1 && !sent);
 reset();alloc_fail=1;assert(message(0x103)!=0 && !freed && !sent);
 reset();assert(message(0xff01)==64 && !sent); /* worker termination excluded */
 reset();live.slots[42]=1;assert(cleanup()==73 && !cancelled && !sent);
 reset();live.slots[18]=1;assert(cleanup()==73 && !cancelled && !sent);
 reset();live.life[3]=240;assert(cleanup()==73 && !cancelled && !sent);
 reset();live.life[0]^=4;assert(cleanup()==73 && !cancelled && !sent);
 reset();dropped=1;assert(cleanup()==75 && !cancelled); /* no false ACK */
 reset();cancel_fail=-1024;assert(cleanup()==74 && cancelled==1);
 reset();reactivate=1;assert(cleanup()==76); /* late callback must fail check */
 reset();assert(cleanup()==0 && cancelled==1 && sent==3); /* delayed setter race */
 reset();redraw_fail=1;assert(cleanup()==78 && redraw_calls==1);
 memset(pixels,0,sizeof pixels);assert(pack_pixels()==28); /* long run splits */
 for(unsigned i=0;i<sizeof pixels;i++)pixels[i]=(unsigned char)(i/2);
 assert(pack_pixels()==0); /* refuse noisy frame before exhausting tmpfs */
 dump_action=fake_dump;
 assert(save_frame("dds-before.rle")==89 && !dumps);
 use_readonly_physical_capture=1;
 assert(save_frame("shooting.rle")==0 && dumps==1);
 assert(save_frame("dds-before.rle")==89 && dumps==1);
 dump_fail=1;assert(save_frame("shooting.rle")==87 && dumps==2);
 use_readonly_physical_capture=0;dump_fail=0;memset(pixels,0,sizeof pixels);
 assert(save_frame("dds-before.rle")==0 && dumps==3);
 shooting_overlay_mode=1;use_readonly_physical_capture=1;
 expected_raw="dds-before.raw";assert(save_frame("dds-before.rle")==0 && dumps==4);
 expected_raw="dds-during.raw";assert(save_frame("dds-during.rle")==0 && dumps==5);
 expected_raw="dds-after.raw";assert(save_frame("dds-after.rle")==0 && dumps==6);
 assert(save_frame("shooting.rle")==89 && dumps==6);
 expected_raw="dds-late.raw";assert(save_frame("dds-late.rle")==0 && dumps==7);
 assert(shooting_region_empty("test")==0);
 for(unsigned y=SHOOTING_Y;y<480;y+=47)for(unsigned x=SHOOTING_X;x<640;x+=639-SHOOTING_X){
  unsigned index=2*(y*640+x);pixels[index]=1;
  assert(shooting_region_empty("occupied")==98);pixels[index]=0;
 }
 pixels[2*((SHOOTING_Y-1)*640+SHOOTING_X)]=1;
 pixels[2*(SHOOTING_Y*640+SHOOTING_X-1)]=1;
 assert(shooting_region_empty("outside")==0);
 puts("PASS: incompressible physical capture saves exact raw frame; display cap and export errors preserved");
 puts("PASS: 13 DDS protocol / cleanup fault cases, 2 RLE bounds (mock native backend)");return 0;
}

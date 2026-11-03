/* ILCE-7C 2.00 diagnostic only: dump MSS requests/state without changing them.
 * Verified k_upm_apicb_mss handles 0x92011c/0 via k_mss_dump_all and returns.
 * Native output is written to the kernel log, not this process's stdout.
 */
typedef unsigned int u32;
extern int printf(const char *, ...);
extern int osal_valloc_msg_wait(u32,void *,u32,int);
extern int osal_snd_sync_msg(u32,void *),osal_free_msg(u32,void *);
int main(void) {
 u32 *m=0;
 int rc=osal_valloc_msg_wait(0x924220,&m,16,1);
 if(rc || !m)return 65;
 m[-1]=0;m[0]=0x92011c;m[1]=0;m[2]=0;m[3]=0;
 rc=osal_snd_sync_msg(0x924220,m);
 printf("POWER_STATUS transport=%d response=%08x\n",rc,m[1]);
 int fr=osal_free_msg(0x924220,m);
 return rc || fr ? 66 : 0;
}

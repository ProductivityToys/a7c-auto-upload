/* ILCE-7C 2.00 ARM EABI boot constructor; no libc/imports/interposed symbols.
 * Checked tmpfs per-boot claim; no writes to media or kernel/firmware.
 */
#ifndef PROBE_DIR
#define PROBE_DIR "/setting/a7c-uploader"
#endif
#ifndef MAX_UPTIME
#define MAX_UPTIME 45
#endif
#ifndef CLAIM_FILE
#define CLAIM_FILE "/tmp_network/a7c-uploader.claim"
#endif
#ifndef WORKER_LIMIT
#define WORKER_LIMIT "350"
#endif
static long sc(long nr,long a,long b,long c,long d) {
 register long r0 __asm__("r0")=a;
 register long r1 __asm__("r1")=b;
 register long r2 __asm__("r2")=c;
 register long r3 __asm__("r3")=d;
 register long r7 __asm__("r7")=nr;
 __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1),"r"(r2),"r"(r3),"r"(r7) : "memory","cc");
 return r0;
}
static unsigned add(char *b,unsigned n,const char *s,unsigned max) {
 for(unsigned i=0;i<max && s[i];i++) b[n++]=s[i];return n;
}
static unsigned num(char *b,unsigned n,unsigned v) {
 char t[10];unsigned i=0;
 do {t[i++]=(char)('0'+v%10);v/=10;}while(v && i<10);
 while(i)b[n++]=t[--i];return n;
}
__attribute__((visibility("hidden"))) void worker_init(void) {
 char up[48],buf[256];unsigned n=0,sec=0,digits=0;long k;
 long fd=sc(5,(long)"/proc/uptime",0,0,0);if(fd<0)return;
 k=sc(3,fd,(long)up,sizeof(up)-1,0);sc(6,fd,0,0,0);
 if(k<=0 || k>=(long)sizeof(up))return;up[k]=0;
 for(unsigned i=0;i<(unsigned)k && i<8;i++) {
  if(up[i]=='.')break;
  if(up[i]<'0'||up[i]>'9')return;
  sec=sec*10+(unsigned)(up[i]-'0');digits++;
  if(sec>=MAX_UPTIME)return;
 }
 if(!digits||up[digits]!='.'||sec>=MAX_UPTIME)return;
 fd=sc(5,(long)PROBE_DIR "/enabled",0,0,0);if(fd<0)return;
 k=sc(3,fd,(long)buf,48,0);sc(6,fd,0,0,0);
 const char token[]="a7c-resident-v1\n";
 if(k!=(long)(sizeof(token)-1))return;
 for(unsigned i=0;i<sizeof(token)-1;i++)if(buf[i]!=token[i])return;
 /* RAM-only per-boot claim. Do not write the similarly named NAND /tmp. */
 char mounts[4096];fd=sc(5,(long)"/proc/mounts",0,0,0);if(fd<0)return;
 k=sc(3,fd,(long)mounts,sizeof(mounts)-1,0);sc(6,fd,0,0,0);if(k<=0||k>=(long)sizeof(mounts)-1)return;
 const char match[]=" /tmp_network tmpfs ";unsigned found=0;
 for(unsigned i=0;i+sizeof(match)-1<=(unsigned)k;i++){unsigned j=0;while(j<sizeof(match)-1&&mounts[i+j]==match[j])j++;if(j==sizeof(match)-1){found=1;break;}}
 if(!found)return;
 /* Exclusive claim BEFORE fork avoids recursion through global preload. */
 fd=sc(5,(long)CLAIM_FILE,193,0600,0);if(fd<0)return;
 n=add(buf,n,token,sizeof(token)-1);
 n=add(buf,n,"trigger_pid=",16);n=num(buf,n,(unsigned)sc(20,0,0,0,0));
 n=add(buf,n," ppid=",8);n=num(buf,n,(unsigned)sc(64,0,0,0,0));
 n=add(buf,n,"\nuptime=",12);n=add(buf,n,up,47);
 sc(4,fd,(long)buf,n,0);sc(6,fd,0,0,0);
 long child=sc(2,0,0,0,0); /* fork */
 if(child<0)return; /* Claim deliberately remains: fail closed. */
 if(child>0) {
  /* Intermediate child only performs setsid/fork/exit. Never wait for worker. */
  for(unsigned tries=0;tries<3;tries++) {
   long w=sc(114,child,0,0,0);if(w!=-4)break; /* wait4; EINTR */
  }
  return;
 }
 if(sc(66,0,0,0,0)<0) {sc(1,111,0,0,0);return;} /* setsid */
 long daemon=sc(2,0,0,0,0);
 if(daemon!=0) {sc(1,daemon<0?112:0,0,0,0);return;}
 /* Do not leak the host executable's inherited descriptors into the worker. */
 for(long f=0;f<4096;f++)sc(6,f,0,0,0);
 long nullfd=sc(5,(long)"/dev/null",2,0,0);
 if(nullfd!=0) {sc(1,113,0,0,0);return;}
 sc(63,0,1,0,0);sc(63,0,2,0,0); /* dup2 */
 char *argv[]={"busybox","ash",PROBE_DIR "/supervisor.sh",0};
 char *env[]={"PATH=/bin:/usr/bin","HOME=/","LC_ALL=C",0};
 sc(11,(long)"/bin/busybox",(long)argv,(long)env,0);
 sc(1,114,0,0,0);
}

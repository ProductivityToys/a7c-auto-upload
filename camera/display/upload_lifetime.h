/* Fixed upload request lifetime and independent guardian pipe protocol.
 * No media/credentials or native writes. Runtime files are on owned tmpfs.
 */
#ifndef DDS_UPLOAD_LIFETIME_H
#define DDS_UPLOAD_LIFETIME_H
#ifndef DDS_UPLOAD_RAM
#define DDS_UPLOAD_RAM "/setting/a7c-uploader/ram/"
#endif
#ifndef DDS_DISPLAY_RAM
#define DDS_DISPLAY_RAM "/setting/a7c-debug/ram/dds-once/"
#endif
#ifndef DDS_PROC_ROOT
#define DDS_PROC_ROOT "/proc/"
#endif
#ifndef DDS_ACTIVE_WATCHDOG_MS
#define DDS_ACTIVE_WATCHDOG_MS 3000U
#endif
#ifndef DDS_CLEANUP_WATCHDOG_MS
#define DDS_CLEANUP_WATCHDOG_MS 15000U
#endif
struct dds_upload_request {
 u32 owner,start,serial,limit;
 char token[128];unsigned bytes;
};
static int dds_decimal(const char **cursor,u32 *value){
 const char *p=*cursor;u32 n=0;unsigned digits=0;
 while(*p>='0'&&*p<='9'){
  if(++digits>10 || n>(0xffffffffU-(u32)(*p-'0'))/10U)return -1;
  n=n*10U+(u32)(*p++-'0');
 }
 if(!digits)return -1;
 *cursor=p;*value=n;return 0;
}
static int dds_upload_parse(struct dds_upload_request *r){
 const char *p=r->token;
 if(dds_decimal(&p,&r->owner)||*p++!=' '||dds_decimal(&p,&r->start)||
    *p++!=' '||dds_decimal(&p,&r->serial)||*p++!=' '||dds_decimal(&p,&r->limit))return -1;
 if(*p=='\n')p++;
 return *p || r->owner<2 || r->owner>0x7fffffffU || !r->start || !r->serial ||
        r->limit<240 || r->limit>86000 ? -1:0;
}
static int dds_read_small(const char *path,char *out,unsigned capacity){
 int fd=open(path,O_RDONLY);if(fd<0)return -1;
 unsigned used=0;int n=0;
 while(used<capacity-1 && (n=read(fd,out+used,capacity-1-used))>0)used+=(unsigned)n;
 char extra;int overflow=used==capacity-1 && read(fd,&extra,1)!=0;
 close(fd);out[used]=0;
 return n<0 || overflow || !used || strlen(out)!=used ? -1:(int)used;
}
static int dds_upload_bind(struct dds_upload_request *r){
 int n=dds_read_small(DDS_UPLOAD_RAM "display.active",r->token,sizeof r->token);
 if(n<0)return -1;
 r->bytes=(unsigned)n;return dds_upload_parse(r);
}
static int dds_upload_active(const struct dds_upload_request *r){
 char token[128],path[96],stat[1024];
 if(!access(DDS_UPLOAD_RAM "stop",0)||!access(DDS_DISPLAY_RAM "cancel",0))return 0;
 int n=dds_read_small(DDS_UPLOAD_RAM "display.active",token,sizeof token);
 if(n!=(int)r->bytes || memcmp(token,r->token,r->bytes) || kill((int)r->owner,0))return 0;
 snprintf(path,sizeof path,DDS_PROC_ROOT "%u/stat",r->owner);
 if(dds_read_small(path,stat,sizeof stat)<0)return 0;
 const char *p=stat,*end=0;
 while(*p){if(*p==')')end=p;p++;}
 if(!end||end[1]!=' ')return 0;
 p=end+2;
 for(unsigned i=0;i<19;i++){
  while(*p&&*p!=' ')p++;
  if(*p++!=' ')return 0;
 }
 u32 start;
 return !dds_decimal(&p,&start)&&(*p==' '||!*p)&&start==r->start;
}
/* H renews only the short live-display watchdog. C transitions ONCE into the
 * bounded cleanup phase. D acknowledges restored native state; EOF/F/timeout
 * require the independent child to stop the setter and perform cleanup.
 */
static int dds_guard_wait(int fd,int continuous,u32 limit){
 struct pollfd f={fd,1,0};u32 began=millis();int cleaning=0,live=0;
 for(;;){
  u32 elapsed=millis()-began;
  u32 maximum=continuous?limit*1000U+30000U:DDS_CLEANUP_WATCHDOG_MS;
  if(elapsed>=maximum)return 0;
  u32 timeout=continuous&&live&&!cleaning?DDS_ACTIVE_WATCHDOG_MS:DDS_CLEANUP_WATCHDOG_MS;
  if(timeout>maximum-elapsed)timeout=maximum-elapsed;
  if(poll(&f,1,(int)timeout)<=0)return 0;
  char command=0;if(read(fd,&command,1)!=1)return 0;
  if(command=='D')return 1;
  if(continuous&&command=='H'&&!cleaning){live=1;continue;}
  if(continuous&&command=='C'&&!cleaning){cleaning=1;continue;}
  return 0;
 }
}
#endif

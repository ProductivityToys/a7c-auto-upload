/* Optional upload progress on the existing private RAM mount. No media reads,
 * network queries, hashing, threads or persistent writes. The full request
 * token prevents a late update from being displayed by a different upload. */
#ifndef A7C_UPLOAD_PROGRESS_H
#define A7C_UPLOAD_PROGRESS_H
#ifndef A7C_PROGRESS_RAM
#define A7C_PROGRESS_RAM "/setting/a7c-uploader/ram/"
#endif
#ifdef __arm__
extern int rename(const char *,const char *);
#endif
static int progress_read(const char *path,char *out,unsigned cap){
 int fd=open(path,O_RDONLY);if(fd<0)return -1;
 unsigned used=0;int n=0;
 while(used<cap-1){n=read(fd,out+used,cap-1-used);if(n>0)used+=(unsigned)n;else if(n<0&&errno==EINTR)continue;else break;}
 char extra;int overflow=used==cap-1&&read(fd,&extra,1)!=0;
 close(fd);out[used]=0;
 return n<0||overflow||!used||strlen(out)!=used?-1:(int)used;
}
#ifdef A7C_PROGRESS_WRITER
struct upload_progress {char token[128];unsigned bytes,percent;u32 updated;int enabled;};
/* 0..99: FTP completion, remote SIZE, publication and SD receipt still have
 * to finish after the data socket drains. No floating point or u64 division. */
static unsigned progress_percent(u64 sent,u64 expected){
 if(!expected)return 0;
 unsigned lo=0,hi=99;
 while(lo<hi){unsigned mid=(lo+hi+1)/2;if((u64)mid*expected<=sent*100)lo=mid;else hi=mid-1;}
 return lo;
}
static void progress_begin(struct upload_progress *p){
 p->enabled=0;p->bytes=0;p->percent=100;p->updated=millis();
 int n=progress_read(A7C_PROGRESS_RAM "display.active",p->token,sizeof p->token);
 if(n<8||p->token[n-1]!='\n')return;
 unsigned spaces=0;
 for(int i=0;i<n-1;i++){
  char c=p->token[i];if(c==' '){if(!i||p->token[i-1]==' ')return;spaces++;}
  else if(c<'0'||c>'9')return;
 }
 if(spaces!=3||p->token[n-2]==' ')return;
 p->bytes=(unsigned)n;p->enabled=1;
}
static void progress_publish(struct upload_progress *p,u64 sent,u64 expected){
 if(!p->enabled||!expected)return;
 u32 now=millis();if(p->percent!=100&&sent<expected&&now-p->updated<1000)return;
 unsigned percent=progress_percent(sent,expected);p->updated=now;
 if(percent==p->percent)return;
 char row[144];memcpy(row,p->token,p->bytes);
 int n=snprintf(row+p->bytes,sizeof row-p->bytes,"%u\n",percent);
 if(n<1||(unsigned)n>=sizeof row-p->bytes)return;
 int fd=open(A7C_PROGRESS_RAM "display.progress.next",O_WRONLY|O_CREAT|O_TRUNC,0600);
 if(fd<0)return;
 unsigned size=p->bytes+(unsigned)n,off=0;
 while(off<size){int w=write(fd,row+off,size-off);if(w>0)off+=(unsigned)w;else if(w<0&&errno==EINTR)continue;else break;}
 close(fd);
 if(off==size&&!rename(A7C_PROGRESS_RAM "display.progress.next",A7C_PROGRESS_RAM "display.progress"))p->percent=percent;
 else unlink(A7C_PROGRESS_RAM "display.progress.next");
}
#else
static int progress_for_token(const char *token,unsigned bytes,unsigned *percent){
 char row[144];int n=progress_read(A7C_PROGRESS_RAM "display.progress",row,sizeof row);
 if(n<0||(unsigned)n<=bytes)return -1;
 for(unsigned i=0;i<bytes;i++)if(row[i]!=token[i])return -1;
 const char *s=row+bytes;unsigned v=0,count=0;
 while(*s>='0'&&*s<='9'){if(++count>2)return -1;v=v*10+(unsigned)(*s++-'0');}
 if(!count||*s++!='\n'||*s||v>99)return -1;
 *percent=v;return 0;
}
#endif
#endif

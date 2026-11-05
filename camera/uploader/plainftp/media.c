/* Conservative local planner inputs. Consumes fresh native snapshots, not USB
 * mounts/raw devices. Unknown rows and XML shapes fail closed. */
#include "../compat.h"
#include "../sha256.h"
#ifdef __arm__
extern char *strchr(const char*,int),*strstr(const char*,const char*);extern int sscanf(const char*,const char*,...),strncmp(const char*,const char*,unsigned),memcmp(const void*,const void*,unsigned);extern void *memcpy(void*,const void*,unsigned);
extern void qsort(void*,unsigned,unsigned,int (*)(const void*,const void*));
#endif
#include "../photo_path.h"
static char buf[262145],xml[16385];
static int load(const char*path,char*b,unsigned cap){int fd=open(path,O_RDONLY);if(fd<0)return -1;unsigned n=0;for(;;){int r=read(fd,b+n,cap-n);if(r<0&&errno==EINTR)continue;if(r<0||n==cap){close(fd);return -1;}if(!r)break;n+=r;}close(fd);for(unsigned i=0;i<n;i++)if(!b[i])return -1;b[n]=0;return n;}
static void hash(const char*b,unsigned n,char*out){Sha s;sha_init(&s);sha_update(&s,(const unsigned char*)b,n);sha_final(&s,out);}
static int dec(const char*s,u64*out){*out=0;if(!*s)return 0;for(;*s;s++){if(*s<'0'||*s>'9'||*out>1844674407370955161ULL||(*out==1844674407370955161ULL&&*s>'5'))return 0;*out=*out*10+*s-'0';}return 1;}
static char*last(char*b,const char*s){char*p=0,*q=b;while((q=strstr(q,s))){p=q;q++;}return p;}
static char*frame(const char*marker){
 char*p=last(buf,marker);if(!p)return 0;p+=strlen(marker);char*end=strstr(p,"MWF>");if(!end)return 0;*end=0;
 if(strstr(p,"OVERFLOW")||strstr(p,"[ERR")||strstr(p," err")||strstr(p,"Failed to")||strstr(p,"Illegal "))return 0;
 for(char*q=p;*q;q++)if(*q=='\r')*q=' ';return p;
}
static int name(const char*s){if(strlen(s)!=9&&strlen(s)!=12)return 0;if(s[0]!='C')return 0;for(int i=1;i<5;i++)if(s[i]<'0'||s[i]>'9')return 0;return !strcmp(s+5,".MP4")?1:(!strcmp(s+5,"M01.XML")?2:0);}
struct Entry {u64 size;char stamp[20];int seen;};
static struct Entry entries[10000][2];
static unsigned order[10000];
static int newest_first(const void*a,const void*b){
 unsigned i=*(const unsigned*)a,j=*(const unsigned*)b;
 int c=strcmp(entries[j][0].stamp,entries[i][0].stamp);
 if(!c)c=strcmp(entries[j][1].stamp,entries[i][1].stamp);
 return c?c:(i<j?1:i>j?-1:0);
}
static int directory(const char*drive,const char*path,int newest){
 if(strlen(drive)!=1||*drive<'A'||*drive>'Z'||load(path,buf,sizeof(buf)-1)<0)return 90;
 char marker[80];snprintf(marker,sizeof(marker),"IFSYS dir %s:/PRIVATE/M4ROOT/CLIP",drive);char*p=frame(marker);if(!p)return 90;
 for(char*line=p;line&&*line;){char*next=strchr(line,'\n');if(next)*next++=0;
  if(!strncmp(line,"[IFSYS]",7)){
   char attr[7],size[32],date[11],clock[9],file[32];int end=0;
   if(sscanf(line,"[IFSYS]%6s %31s %10s %8s %31s %n",attr,size,date,clock,file,&end)!=5||!end||line[end])return 90;
   int kind=name(file);u64 bytes;if(!kind||strlen(attr)!=6||attr[0]!='a'||!dec(size,&bytes)||strlen(date)!=10||strlen(clock)!=8)return 90;
   int id=(file[1]-'0')*1000+(file[2]-'0')*100+(file[3]-'0')*10+file[4]-'0';struct Entry*e=&entries[id][kind-1];if(e->seen)return 90;e->seen=1;e->size=bytes;snprintf(e->stamp,sizeof(e->stamp),"%sT%s",date,clock);
  }else {for(char*q=line;*q;q++)if(*q!=' '&&*q!='\t')return 90;}
  line=next;
 }
 unsigned count=0;
 for(unsigned i=0;i<10000;i++)if(entries[i][0].seen){
  struct Entry*v=&entries[i][0],*x=&entries[i][1];
  if(!x->seen||!v->size||v->size>274877906944ULL||!x->size||x->size>16384)return 90;
  order[count++]=i;
 }
 if(newest)qsort(order,count,sizeof(order[0]),newest_first);
 for(unsigned k=0;k<count;k++){unsigned i=order[k];struct Entry*v=&entries[i][0],*x=&entries[i][1];
  char out[150];int n=snprintf(out,sizeof(out),"C%04u.MP4 %llu C%04uM01.XML %llu %s %s\n",i,v->size,i,x->size,v->stamp,x->stamp);if(write(1,out,n)!=n)return 74;
 }return 0;
}
static int info(const char*drive,const char*path,int photos){
 if(strlen(drive)!=1||load(path,buf,sizeof(buf)-1)<0)return 90;char*p=frame("IFSYS info");if(!p)return 90;
 const char*banner="******** Fsys - IFSYS   VER:109 CATEGORY:MAIN TYPE:COM CXD:COM ********";
 char*first=strstr(p,banner);char*second=first?strstr(first+strlen(banner),banner):0;if(!second||strstr(second+strlen(banner),banner))return 90;
 int sd=0;char internal=0,card[512];card[0]=0;
 for(char*q=p;(q=strstr(q,"drive info : "));){char*end=strstr(q+1,"drive info : ");char*opened=strstr(q,"open file info :");if(!end||(opened&&opened<end))end=opened;if(!end)end=second;if(end<=q)return 90;char save=*end;*end=0;
  if(strstr(q,"mount device name = \"/dev/mmca\"")){
   char reported=0;if(sscanf(q,"drive info : %c(%c)",&reported,&internal)!=2||reported!=*drive||++sd!=1){*end=save;return 90;}
   char*s=strstr(q,"  drive status      = ");if(!s||strncmp(s+22,"mount",5)){*end=save;return 90;}
   char*id=strstr(q,"  ID                = "),*cidend=id?strstr(id,"  drive status"):0;if(!id||!cidend||cidend-id>400){*end=save;return 90;}
   int n=snprintf(card,sizeof(card),"%c:%c:",reported,internal);unsigned len=cidend-id;memcpy(card+n,id,len);card[n+len]=0;
  }*end=save;q=end;
 }
 if(sd!=1)return 90;
 char prefix[40],photo_prefix[20];snprintf(prefix,sizeof(prefix),"\"%c:\\PRIVATE\\M4ROOT\\CLIP\\",internal);snprintf(photo_prefix,sizeof photo_prefix,"\"%c:\\DCIM\\",internal);
 for(char*q=p;(q=strstr(q,"open file info :"));){char*end=strstr(q+1,"open file info :");if(!end)end=second;if(end<=q)return 90;char save=*end;*end=0;
  char*s=strstr(q,"  status            = "),*n=strstr(q,"  file & ext name   = ");if(!s||!n){*end=save;return 90;}
  char*e=strchr(s,'\n');if(!e){*end=save;return 90;}char c=*e;*e=0;int writing=strstr(s,"write")!=0;*e=c;
  if(writing&&(strstr(n,prefix)||(photos&&strstr(n,photo_prefix)))){*end=save;return 90;}*end=save;q=end;
 }
 char digest[65];hash(card,strlen(card),digest);digest[64]='\n';return write(1,digest,65)==65?0:74;
}
static int space(char c){return c==' '||c=='\t'||c=='\r'||c=='\n';}
static int nc(char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c==':';}
/* Strict bounded tokenizer: balanced elements, unique attributes, no entities,
 * comments/DTD or nested namespace rebinding. Deliberately not general XML. */
static int metadata(const char*path,const char*size){
 u64 bytes;if(!dec(size,&bytes)||!bytes||bytes>274877906944ULL)return 90;
 int length=load(path,xml,16384);if(length<=0||strstr(xml,"<!")||strchr(xml,'&'))return 90;
 char xmlhash[65],umid[65]={0};hash(xml,length,xmlhash);
 char stack[32][64];unsigned depth=0,roots=0,target=0,duration=0,device=0,ends=0;u64 frames=0,endframe=0;char*p=xml;
 while(*p){if(space(*p)){p++;continue;}if(*p!='<')return 90;p++;
  if(*p=='?'){if(roots||depth||strncmp(p,"?xml ",5))return 90;char*q=strstr(p,"?>");if(!q)return 90;p=q+2;continue;}
  int closing=*p=='/';if(closing)p++;char tag[64];unsigned n=0;while(nc(*p)){if(n>=63)return 90;tag[n++]=*p++;}tag[n]=0;if(!n||strchr(tag,':'))return 90;
  if(closing){while(space(*p))p++;if(*p++!='>'||!depth||strcmp(tag,stack[depth-1]))return 90;depth--;continue;}
  char keys[32][64],values[32][256];unsigned count=0;
  while(space(*p)){while(space(*p))p++;if(*p=='/'||*p=='>')break;if(count>=32)return 90;n=0;while(nc(*p)){if(n>=63)return 90;keys[count][n++]=*p++;}keys[count][n]=0;if(!n)return 90;
   for(unsigned i=0;i<count;i++)if(!strcmp(keys[i],keys[count]))return 90;
   while(space(*p))p++;if(*p++!='=')return 90;while(space(*p))p++;char quote=*p++;if(quote!='"'&&quote!='\'')return 90;n=0;
   while(*p&&*p!=quote){if(n>=255||*p=='<'||(unsigned char)*p<32)return 90;values[count][n++]=*p++;}values[count][n]=0;if(*p++!=quote)return 90;
   if(depth&&!strncmp(keys[count],"xmlns",5))return 90;count++;
  }
  int self=*p=='/';if(self)p++;if(*p++!='>')return 90;
  const char *umidvalue=0,*value=0,*status=0,*frame=0,*model=0,*ns=0;
  for(unsigned i=0;i<count;i++){if(!strcmp(keys[i],"umidRef"))umidvalue=values[i];if(!strcmp(keys[i],"value"))value=values[i];if(!strcmp(keys[i],"status"))status=values[i];if(!strcmp(keys[i],"frameCount"))frame=values[i];if(!strcmp(keys[i],"modelName"))model=values[i];if(!strcmp(keys[i],"xmlns"))ns=values[i];}
  if(!depth){if(++roots!=1||strcmp(tag,"NonRealTimeMeta")||!ns||strcmp(ns,"urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20")||self)return 90;}
  if(depth==1&&!strcmp(tag,"TargetMaterial")){if(++target!=1||!self||!umidvalue||strlen(umidvalue)!=64)return 90;for(unsigned i=0;i<64;i++){char c=umidvalue[i];if(c>='a'&&c<='f')c-=32;if(!((c>='0'&&c<='9')||(c>='A'&&c<='F')))return 90;umid[i]=c;}}
  if(depth==1&&!strcmp(tag,"Duration")){if(++duration!=1||!self||!value||!dec(value,&frames)||!frames)return 90;}
  if(depth==1&&!strcmp(tag,"Device")){if(++device!=1||!self||!model||strcmp(model,"ILCE-7C"))return 90;}
  if(depth==2&&!strcmp(stack[1],"LtcChangeTable")&&!strcmp(tag,"LtcChange")&&status&&!strcmp(status,"end")){if(++ends!=1||!self||!frame||!dec(frame,&endframe))return 90;}
  if(!self){if(depth>=32)return 90;memcpy(stack[depth++],tag,strlen(tag)+1);}
 }
 if(depth||roots!=1||target!=1||duration!=1||device!=1||ends!=1||endframe!=frames-1)return 90;
 char key[180],out[65];int n=snprintf(key,sizeof(key),"%s:%llu:%s",umid,bytes,xmlhash);hash(key,n,out);out[64]='\n';return write(1,out,65)==65?0:74;
}
/* Directory-only identity. XML columns are parsed only to consume the existing
 * listing row; they are not identity inputs and the XML file is never opened. */
static int row_identity(const char *row){
 char video[32],size[32],sidecar[32],xsize[32],stamp[32],xstamp[32];int end=0;u64 bytes;
 if(sscanf(row,"%31s %31s %31s %31s %31s %31s%n",video,size,sidecar,xsize,stamp,xstamp,&end)!=6||!end||row[end]||(name(video)!=1&&!a7c_photo_path(video))||!dec(size,&bytes)||!bytes||bytes>274877906944ULL)return 90;
 if(a7c_photo_path(video)&&(strcmp(sidecar,"-")||strcmp(xsize,"0")||strcmp(xstamp,"-")))return 90;
 if(strlen(stamp)!=19)return 90;
 for(unsigned i=0;i<19;i++){
  char want=i==4||i==7?'-':i==10?'T':i==13||i==16?':':0;
  if(want?stamp[i]!=want:(stamp[i]<'0'||stamp[i]>'9'))return 90;
 }
 char key[120],out[65];int n=snprintf(key,sizeof key,"a7c-file-v1:%s:%llu:%s",video,bytes,stamp);hash(key,n,out);out[64]='\n';return write(1,out,65)==65?0:74;
}
struct Photo {char path[27],stamp[20];u64 bytes;};
static struct Photo photos[4000];
static int photo_compare(const void *a,const void *b){return strcmp(((const struct Photo*)a)->path,((const struct Photo*)b)->path);}
/* Exact native command line prevents a DCIM root from matching a subfolder.
 * Restore the reply boundary before looking up the next completed reply. */
static char *photo_frame(const char *marker,char **end){
 char *p=last(buf,marker);if(!p)return 0;p+=strlen(marker);*end=strstr(p,"MWF>");if(!*end)return 0;**end=0;
 if(strstr(p,"OVERFLOW")||strstr(p,"[ERR")||strstr(p,"Failed to")||strstr(p,"Illegal ")||strstr(p,"Can't open")){**end='M';return 0;}
 return p;
}
static int photo_directory(const char *drive,const char *path){
 if(strlen(drive)!=1||*drive<'A'||*drive>'Z'||load(path,buf,sizeof buf-1)<0)return 90;
 char folders[900][9],marker[80],*end;unsigned count=0,total=0;
 snprintf(marker,sizeof marker,"IFSYS dir %s:/DCIM\r\n",drive);
 char *p=photo_frame(marker,&end);if(!p)return 90;
 int rc=a7c_photo_folders(p,folders,&count);*end='M';if(rc)return rc;
 for(unsigned folder=0;folder<count;folder++){
  snprintf(marker,sizeof marker,"IFSYS dir %s:/DCIM/%s\r\n",drive,folders[folder]);p=photo_frame(marker,&end);if(!p)return 90;
  for(char *line=p;*line;){
   char *next=strchr(line,'\n');unsigned n=next?(unsigned)(next-line):strlen(line);char row[1025];
   if(n>=sizeof row)return 90;memcpy(row,line,n);row[n]=0;
   if(!strncmp(row,"[IFSYS]",7)){
    char attr[7],size[32],date[11],clock[9],file[32];int used=0;u64 bytes;
    if(sscanf(row,"[IFSYS]%6s %31s %10s %8s %31s %n",attr,size,date,clock,file,&used)!=5||!used||row[used]||strlen(attr)!=6||!dec(size,&bytes))return 90;
    if(attr[0]=='a'&&a7c_photo_file(file)){
     if(!bytes||bytes>274877906944ULL||strlen(date)!=10||strlen(clock)!=8||total==4000)return 90;
     struct Photo *photo=&photos[total++];photo->bytes=bytes;
     snprintf(photo->path,sizeof photo->path,"DCIM/%s/%s",folders[folder],file);
     snprintf(photo->stamp,sizeof photo->stamp,"%sT%s",date,clock);
    }
   }else for(char *q=row;*q;q++)if(!space(*q))return 90;
   if(!next)break;line=next+1;
  }
  *end='M';
 }
 qsort(photos,total,sizeof photos[0],photo_compare);
 for(unsigned i=1;i<total;i++)if(!strcmp(photos[i-1].path,photos[i].path))return 90;
 for(unsigned i=0;i<total;i++){
  char out[120];int n=snprintf(out,sizeof out,"%s %llu - 0 %s -\n",photos[i].path,photos[i].bytes,photos[i].stamp);
  if(write(1,out,n)!=n)return 74;
 }
 return 0;
}
struct Ordered {char *row,*stamp;};
static struct Ordered ordered[4000];
static int ordered_compare(const void *a,const void *b){
 const struct Ordered *x=a,*y=b;int c=memcmp(y->stamp,x->stamp,19);
 return c?c:strcmp(x->row,y->row);
}
/* Sort the already-parsed mixed queue by its fifth field. The camera's sort
 * applet did not order the full queue as expected; no external index needed. */
static int order_rows(const char *path){
 if(load(path,buf,sizeof buf-1)<0)return 90;unsigned count=0;
 for(char *line=buf;*line;){
  char *next=strchr(line,'\n');if(next)*next=0;
  char file[32],size[32],sidecar[32],xsize[32],stamp[32],xstamp[32];int at=0,end=0;u64 bytes;
  if(count==4000||sscanf(line,"%31s %31s %31s %31s %n%31s %31s%n",file,size,sidecar,xsize,&at,stamp,xstamp,&end)!=6||!end||line[end]||(name(file)!=1&&!a7c_photo_path(file))||!dec(size,&bytes)||!bytes||strlen(stamp)!=19)return 90;
  for(unsigned i=0;i<19;i++){
   char want=i==4||i==7?'-':i==10?'T':i==13||i==16?':':0;
   if(want?stamp[i]!=want:(stamp[i]<'0'||stamp[i]>'9'))return 90;
  }
  ordered[count++]=(struct Ordered){line,line+at};
  if(!next)break;line=next+1;
 }
 qsort(ordered,count,sizeof ordered[0],ordered_compare);
 for(unsigned i=0;i<count;i++){
  unsigned n=strlen(ordered[i].row);
  if(write(1,ordered[i].row,n)!=(int)n||write(1,"\n",1)!=1)return 74;
 }
 return 0;
}
/* 0 present, 10 absent, 90 owned-name conflict, 75 listing unreadable.
 * The native frontend can interleave asynchronous console messages (e.g.
 * "[MWF]  [RsrcAcsr] already Acquired!") into a row. Such a transcript proves
 * neither presence nor absence: report it as retryable, never as absent. */
static int exists(const char*drive,const char*filename,const char*path){
 if(strlen(drive)!=1)return 90;
 if(load(path,buf,sizeof(buf)-1)<0)return 75;
 char marker[40];snprintf(marker,sizeof(marker),"IFSYS dir %s:/",drive);char*p=frame(marker);if(!p)return 75;int found=0;
 for(char*line=p;line&&*line;){char*next=strchr(line,'\n');if(next)*next++=0;
  if(!strncmp(line,"[IFSYS]",7)){char attr[7],size[32],date[11],clock[9];int end=0;u64 bytes;
   if(sscanf(line,"[IFSYS]%6s %31s %10s %8s %n",attr,size,date,clock,&end)!=4||!end||strlen(attr)!=6||!dec(size,&bytes))return 75;
   /* FAT long names, including Windows' System Volume Information, are the
    * entire remainder of the row. Only compare the exact owned 8.3 receipt;
    * unrelated directory names may contain spaces or UTF-8 characters. */
   char*file=line+end;unsigned length=strlen(file);
   while(length&&(file[length-1]==' '||file[length-1]=='\t'))file[--length]=0;
   if(!length||length>1024)return 75;
   if(!strcmp(file,filename)){if(found++)return 90;if(attr[0]!='a'||bytes>512)return 90;}
  }else {for(char*q=line;*q;q++)if(*q!=' '&&*q!='\t')return 75;}line=next;
 }return found?0:10;
}
int main(int argc,char**v){(void)millis;if(argc==3&&!strcmp(v[1],"row-identity"))return row_identity(v[2]);if(argc==3&&!strcmp(v[1],"order"))return order_rows(v[2]);if(argc==5&&!strcmp(v[1],"exists"))return exists(v[2],v[3],v[4]);if(argc==4&&!strcmp(v[1],"dir"))return directory(v[2],v[3],0);if(argc==4&&!strcmp(v[1],"newest"))return directory(v[2],v[3],1);if(argc==4&&!strcmp(v[1],"photos"))return photo_directory(v[2],v[3]);if(argc==4&&(!strcmp(v[1],"info")||!strcmp(v[1],"info-photos")))return info(v[2],v[3],!strcmp(v[1],"info-photos"));if(argc==4&&!strcmp(v[1],"identity"))return metadata(v[2],v[3]);return 64;}

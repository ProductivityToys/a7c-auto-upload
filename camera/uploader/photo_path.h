/* DCF photo paths only: shared by the native read whitelist and local planner.
 * No arbitrary paths, shell characters, thumbnails or sidecars. */
#ifndef A7C_PHOTO_PATH_H
#define A7C_PHOTO_PATH_H
static inline int a7c_photo_folder(const char *s){
 if(strlen(s)!=8||s[0]<'1'||s[0]>'9'||s[1]<'0'||s[1]>'9'||s[2]<'0'||s[2]>'9')return 0;
 for(unsigned i=3;i<8;i++)if(!((s[i]>='A'&&s[i]<='Z')||(s[i]>='0'&&s[i]<='9')||s[i]=='_'))return 0;
 return 1;
}
static inline int a7c_photo_file(const char *s){
 if(strlen(s)!=12||s[8]!='.'||(strcmp(s+9,"JPG")&&strcmp(s+9,"ARW")))return 0;
 for(unsigned i=0;i<8;i++)if(!((s[i]>='A'&&s[i]<='Z')||(s[i]>='0'&&s[i]<='9')||s[i]=='_'))return 0;
 for(unsigned i=4;i<8;i++)if(s[i]<'0'||s[i]>'9')return 0;
 return 1;
}
static inline int a7c_photo_path(const char *s){
 if(strlen(s)!=26||strncmp(s,"DCIM/",5)||s[13]!='/')return 0;
 char folder[9];for(unsigned i=0;i<8;i++)folder[i]=s[5+i];folder[8]=0;
 return a7c_photo_folder(folder)&&a7c_photo_file(s+14);
}
/* A completed DCIM listing. Only bounded, valid DCF subdirectories are read. */
static inline int a7c_photo_folders(const char *reply,char folders[900][9],unsigned *count){
 *count=0;
 for(const char *p=reply;(p=strstr(p,"[IFSYS]"));p+=7){
  char attr[7],size[32],date[11],clock[9],folder[32];int end=0;
  if(sscanf(p,"[IFSYS]%6s %31s %10s %8s %31s%n",attr,size,date,clock,folder,&end)!=5||!end)return 90;
  if(attr[1]!='d'||!a7c_photo_folder(folder))continue;
  if(p[end]&&p[end]!='\r'&&p[end]!='\n')return 90;
  if(*count==900)return 90;
  for(unsigned i=0;i<*count;i++)if(!strcmp(folder,folders[i]))return 90;
  for(unsigned i=0;i<9;i++)folders[*count][i]=folder[i];
  ++*count;
 }
 return 0;
}
#endif

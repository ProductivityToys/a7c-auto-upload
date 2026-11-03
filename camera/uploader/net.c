/* Tracked FTP child: bounded lifetime, cancellation reaps it before returning.
 * Avoid a shell/timeout grandchild surviving network failure for a large clip.
 */
#include "compat.h"
#ifndef BB_EXEC
#define BB_EXEC "/bin/busybox"
#endif
#ifndef TOKEN_FILE
#define TOKEN_FILE "/setting/a7c-uploader/token"
#endif
#ifndef FTP_PORT
#define FTP_PORT "21214"
#endif
static volatile int stopped=0;
static void stop(int sig){stopped=sig;}
int main(int argc,char**argv){
 if(argc!=5)return 64;
 int get=!strcmp(argv[1],"get"),put=!strcmp(argv[1],"put");if(!get&&!put)return 64;
 int seconds=atoi(argv[4]);if(seconds<1||seconds>86400)return 64;
 char token[66];int fd=open(TOKEN_FILE,O_RDONLY);if(fd<0)return 65;
 int n=read(fd,token,sizeof(token));close(fd);if(n!=65||token[64]!='\n')return 65;
 for(int i=0;i<64;i++)if(!((token[i]>='0'&&token[i]<='9')||(token[i]>='a'&&token[i]<='f')))return 65;
 token[64]=0;signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
 int child=fork();if(child<0)return 66;
 if(!child){char*a[]={"busybox",get?"ftpget":"ftpput","-P",FTP_PORT,"-u","a7c","-p",token,"192.168.5.190",get?argv[3]:argv[2],get?argv[2]:argv[3],0};execv(BB_EXEC,a);_exit(127);}
 for(int i=0;i<66;i++)token[i]=0;
 u32 start=millis();int status=0,owner=getppid();
 for(;;){int rc=waitpid(child,&status,1);if(rc==child)return (status&127)?128+(status&127):(status>>8)&255;if(rc<0&&errno!=EINTR)return 67;if(getppid()!=owner)stopped=SIGTERM;if(stopped||millis()-start>=(u32)seconds*1000)break;usleep(100000);}
 kill(child,SIGTERM);
 for(int i=0;i<10;i++){if(waitpid(child,&status,1)==child)return stopped?128+stopped:124;usleep(100000);}
 kill(child,9);while(waitpid(child,&status,0)<0&&errno==EINTR){}return stopped?128+stopped:124;
}

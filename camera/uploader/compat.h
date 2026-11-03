#ifndef A7C_COMPAT_H
#define A7C_COMPAT_H
typedef unsigned int u32; typedef unsigned long long u64;
#ifdef __arm__
extern int open(const char*,int,...),close(int),pipe(int*),fork(void),dup2(int,int),execv(const char*,char*const*),kill(int,int),waitpid(int,int*,int),getpid(void),getppid(void),access(const char*,int),unlink(const char*),poll(void*,unsigned long,int),read(int,void*,unsigned),write(int,const void*,unsigned),snprintf(char*,unsigned,const char*,...),strcmp(const char*,const char*),atoi(const char*),clock_gettime(int,void*),usleep(unsigned);
extern unsigned strlen(const char*),sleep(unsigned); extern unsigned long long strtoull(const char*,char**,int);
extern int *__errno_location(void); extern void _exit(int); extern void (*signal(int,void (*)(int)))(int);
#define errno (*__errno_location())
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 64
#define O_EXCL 128
#define O_TRUNC 512
#define O_NONBLOCK 2048
#define EAGAIN 11
#define EINTR 4
#define SIGPIPE 13
#define SIGTERM 15
#define SIGINT 2
#define SIG_IGN ((void (*)(int))1)
struct pollfd {int fd;short events,revents;};
struct timespec {long tv_sec,tv_nsec;};
#define CLOCK_MONOTONIC 1
#else
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <poll.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/wait.h>
#endif
static u32 millis(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))_exit(74);return (u32)t.tv_sec*1000+(u32)t.tv_nsec/1000000;}
#endif

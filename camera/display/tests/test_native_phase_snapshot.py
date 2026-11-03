"""Check fixed read-only mapping and failure cleanup without camera access."""
import subprocess,tempfile,unittest
from pathlib import Path

class SnapshotTests(unittest.TestCase):
 def test_native_shell_mapping_parser(self):
  source=(Path(__file__).resolve().parents[1]/'module/native_phase_action.sh').read_text()
  fragment=source[source.index(' base=\n'):source.index(' echo SAMPLE_BEGIN')]
  with tempfile.TemporaryDirectory() as tmp:
   maps=Path(tmp)/'maps'
   fragment=fragment.replace('/proc/$p/maps',str(maps))
   line='05400000-05440000 r-xp 00000000 fc:0f 123 /usr/lib/libObj.so\n'
   for fixture,rc,output in ((line,0,'05400000'),(line+line,95,''),('',95,'')):
    maps.write_text(fixture)
    result=subprocess.run(['sh','-c','sample() {\n'+fragment+'\necho "$base";\n}; sample'],capture_output=True,text=True)
    self.assertEqual(result.returncode,rc)
    self.assertEqual(result.stdout.strip(),output)

 def test_read_scope_and_cleanup(self):
  header=Path(__file__).resolve().parents[1]/'module/native_phase_snapshot.h'
  source=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned U;
static U phase_mapping=0x040c3000, page[1024];
static int opened,unmapped,closed,fail_map,direct,native,slept,fail_sleep;
static int rd(U a,void *p,U n){
 if(native){
  U value=0;const unsigned char code[8]={0x2d,0xe9,0xf0,0x41,0x82,0xb0,0x1a,0x4e};
  if(a==0x1000000){value=0x464c457f;assert(n==4);memcpy(p,&value,n);return 0;}
  if(a==0x1000000+0x898380){assert(n==8);memcpy(p,code,n);return 0;}
  if(a==0x1550c){assert(n==8);memset(p,0,n);return 0;}
  if(a==0x1000000+0x1488e84){value=phase_mapping+0x390;assert(n==4);memcpy(p,&value,n);return 0;}
  if(a==0x1000000+0x1488fdc){assert(n==4);memset(p,0,n);return 0;}
 }
 if(direct){memset(p,0x42,n);return 0;}return -1;
}
int usleep(unsigned delay){
 assert(delay==1000);slept++;page[0x390/4+3]++;
 if(slept==100)memcpy(page+0x390/4+5,"drawFramebuffer ",16);
 if(slept==200)memcpy(page+0x390/4+5,"sleep           ",16);
 return fail_sleep&&slept==5?-1:0;
}
static int fake_open(const char *p,int flags,...){assert(!strcmp(p,"/dev/mem")&&flags==0);opened++;return 17;}
static int fake_close(int fd){assert(fd==17);closed++;return 0;}
void *mmap64(void *p,unsigned size,int prot,int flags,int fd,long long offset){
 assert(!p&&size==4096&&prot==1&&flags==1&&fd==17&&offset==0x03103000LL);
 return fail_map?(void *)-1:page;
}
int munmap(void *p,unsigned size){assert(p==page&&size==4096);unmapped++;return 0;}
#define open fake_open
#define close fake_close
#include "HEADER"
int main(void){U out[9];
 for(U n=0;n<9;n++)page[0x390/4+n]=100+n;
 assert(native_phase_read(phase_mapping+0x390,out)==0);
 for(U n=0;n<9;n++)assert(out[n]==100+n);
 assert(opened==1&&unmapped==1&&closed==1);
 assert(native_phase_read(phase_mapping+0x394,out)==-1&&opened==1);
 fail_map=1;assert(native_phase_read(phase_mapping+0x390,out)==-1);
 assert(opened==2&&unmapped==1&&closed==2);
 phase_mapping=0;assert(native_phase_read(0x390,out)==-1&&opened==2);
 direct=1;assert(native_phase_read(0x1000,out)==0&&opened==2&&out[0]==0x42424242);
 direct=fail_map=0;native=1;phase_mapping=0x040c3000;
 memcpy(page+0x390/4+5,"sleep           ",16);
 opened=closed=unmapped=0;
 assert(native_phase_burst(0x1000000)==0&&slept==400);
 assert(opened==3&&unmapped==3&&closed==3);
 slept=0;fail_sleep=1;
 assert(native_phase_burst(0x1000000)==85&&slept==5);
 assert(opened==6&&unmapped==6&&closed==6);
 return 0;
}
'''.replace('HEADER',str(header))
  with tempfile.TemporaryDirectory(prefix='a7c-phase-') as tmp:
   root=Path(tmp);(root/'test.c').write_text(source)
   subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined',str(root/'test.c'),'-o',str(root/'test')],check=True,capture_output=True)
   subprocess.run([str(root/'test')],check=True,capture_output=True)

if __name__=='__main__':unittest.main()

"""Optional RAM progress contract: throttling, ownership, large videos and errors."""
from pathlib import Path
import subprocess,tempfile,unittest

SRC=Path(__file__).resolve().parents[2]
class ProgressTests(unittest.TestCase):
 def test_producer_throttle_and_reader_validation(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);token='123 456 7 240\n'
   header='#include "compat.h"\n#include "upload_progress.h"\n'
   writer=p/'writer.c';writer.write_text('#include <assert.h>\n#define A7C_PROGRESS_WRITER 1\n'+header+r'''
int main(void){
 struct upload_progress p;progress_begin(&p);assert(p.enabled);
 progress_publish(&p,0,1000);assert(p.percent==0);
 p.updated=millis()-1000;progress_publish(&p,420,1000);assert(p.percent==42);
 progress_publish(&p,700,1000);assert(p.percent==42);
 p.updated=millis()-1000;progress_publish(&p,700,1000);assert(p.percent==70);
 progress_publish(&p,1000,1000);assert(p.percent==99);
 assert(progress_percent(0,274877906944ULL)==0);
 assert(progress_percent(137438953472ULL,274877906944ULL)==50);
 assert(progress_percent(274877906944ULL,274877906944ULL)==99);
 return 0;
}
''')
   reader=p/'reader.c';reader.write_text(header+r'''
int main(void){unsigned p=0;(void)millis();if(progress_for_token("123 456 7 240\n",14,&p))return 42;printf("%u\n",p);return 0;}
'''.replace(',14,',','+str(len(token))+','))
   for name in ['writer','reader']:
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(SRC),'-DA7C_PROGRESS_RAM="'+str(p)+'/"',str(p/(name+'.c')),'-o',str(p/name)],check=True)
   (p/'display.active').write_text(token)
   subprocess.run([str(p/'writer')],check=True)
   self.assertEqual((p/'display.progress').read_text(),token+'99\n')
   self.assertFalse((p/'display.progress.next').exists())
   for row,expected in [(token+'0\n',0),(token+'42\n',42),(token+'99\n',99),
                        (token+'100\n',None),(token+'42',None),(token+'4x\n',None),
                        ('999 456 7 240\n42\n',None),(token+'42\nextra',None),(token+'42\0\n',None)]:
    (p/'display.progress').write_text(row)
    result=subprocess.run([str(p/'reader')],capture_output=True,text=True)
    if expected is None:self.assertEqual(result.returncode,42,row)
    else:self.assertEqual(result.stdout,str(expected)+'\n')

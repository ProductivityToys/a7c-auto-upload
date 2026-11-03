"""Exercise the production pause body at the timeout/retirement boundary.

Native thread identity, sleeps and handoff results are controlled. This checks
our returned completion status, not native GPU completion or crash causality.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path


class PauseCompletionTests(unittest.TestCase):
    def test_retirement_completion(self):
        source = (Path(__file__).resolve().parents[1]/'module/rect_module.c').read_text()
        body = source[source.index('static int pause_drawing(U reason){'):source.index('\n#endif\nAPI int IM_SAMPLE_SO_sus')]
        fixture = r'''
#include <assert.h>
#include <stdarg.h>
typedef unsigned U;
static struct { int initialized; } handoff;
static struct { unsigned tid; int restore_rc,capture_rc; } marker;
static struct { unsigned stopped; } a7c_native_marker;
#define MARKER marker
static int pause_rc,stop_rc,pauses,stops,sleeps,same_thread;
static int syscall(int op,...){
 if(op==224)return same_thread?2:1;
 assert(op==162);sleeps++;return 0;
}
static int series_pause(void *s,U reason){assert(s==&handoff&&reason==2);pauses++;return pause_rc;}
static int series_stop(void *s){assert(s==&handoff);stops++;return stop_rc;}
BODY
static void reset(int pending,int retired){
 handoff.initialized=1;marker.tid=2;marker.restore_rc=-999;marker.capture_rc=0;
 a7c_native_marker.stopped=0;pauses=stops=sleeps=same_thread=0;
 pause_rc=pending;stop_rc=retired;
}
int main(void){
 reset(0,0);assert(pause_drawing(2)==0&&pauses==1&&!stops&&!sleeps);
 /* Draw drains after the last pause check, before retirement reads busy. */
 reset(1,0);assert(pause_drawing(2)==0&&pauses==51&&stops==1&&sleeps==50);
 assert(a7c_native_marker.stopped==2&&marker.restore_rc==0&&marker.capture_rc==-23);
 reset(1,1);assert(pause_drawing(2)==1&&stops==1&&sleeps==50);
 reset(1,-2);assert(pause_drawing(2)==-2&&stops==1);
 reset(1,1);same_thread=1;assert(pause_drawing(2)==1&&pauses==1&&!sleeps);
 reset(0,0);handoff.initialized=0;assert(pause_drawing(2)==0&&!pauses&&!stops);
 return 0;
}
'''.replace('BODY', body)
        with tempfile.TemporaryDirectory(prefix='a7c-pause-') as tmp:
            p = Path(tmp)
            (p/'fixture.c').write_text(fixture)
            subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'fixture.c'),'-o',str(p/'fixture')],check=True,capture_output=True)
            result = subprocess.run([str(p/'fixture')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__ == '__main__':
    unittest.main()

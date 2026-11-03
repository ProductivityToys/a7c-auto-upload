"""Run exact rollback in an isolated filesystem populated from a release candidate."""
from pathlib import Path
import os,subprocess,tempfile,unittest
HERE=Path(__file__).resolve().parent
@unittest.skipUnless(os.environ.get('A7C_NATIVE_PACKAGE'),'requires built release candidate')
class RollbackTests(unittest.TestCase):
 def test_busy_rejected_then_exact_previous_files_restored(self):
  c=Path(os.environ['A7C_NATIVE_PACKAGE'])
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);p=r/'persistent';d=r/'runtime';u=r/'uploader';n=d/'native-service';k=p/'native-backup-038'
   for q in (p,d,u,n,k):q.mkdir(parents=True,exist_ok=True)
   for f in (c/'payload/display').iterdir():(p/f.name).write_bytes(f.read_bytes())
   for f in (c/'rollback/display').iterdir():(k/f.name).write_bytes(f.read_bytes())
   (u/'stop').touch();(u/'worker.exit').touch();(n/'im.pid').write_text('42\n')
   probe=n/'probe';probe.write_text('#!/bin/sh\nexit 0\n');probe.chmod(0o700)
   bb=r/'bb';bb.write_text('#!/bin/sh\ncase "$1" in pidof) echo 42;; sha256sum) shift; exec shasum -a 256 "$@";; *) exec "$@";; esac\n');bb.chmod(0o700)
   script=HERE.joinpath('rollback-native.sh').read_text().replace('B=/bin/busybox',f'B={bb}').replace('/setting/a7c-display',str(p)).replace('/setting/a7c-debug/ram/dds-once',str(d)).replace('/setting/a7c-uploader/ram',str(u))
   run=r/'run';run.write_text(script)
   active=u/'display.active';active.touch();old=(p/'manifest').read_bytes()
   rejected=subprocess.run(['sh',str(run),'PROBE'],capture_output=True,text=True,timeout=8)
   self.assertIn('ROLLBACK_RC=92',rejected.stdout);self.assertEqual((p/'manifest').read_bytes(),old);active.unlink()
   result=subprocess.run(['sh',str(run),'PROBE'],capture_output=True,text=True,timeout=8)
   self.assertIn('ROLLBACK_RC=0',result.stdout,result.stdout+result.stderr)
   for f in (c/'rollback/display').iterdir():self.assertEqual((p/f.name).read_bytes(),f.read_bytes())
   for name in ('native-start.sh','native-probe','native-module.so'):self.assertFalse((p/name).exists())
   self.assertEqual((u/'native-rollback.log').read_text(),'NATIVE_ROLLBACK_038_OK\n')
if __name__=='__main__':unittest.main()

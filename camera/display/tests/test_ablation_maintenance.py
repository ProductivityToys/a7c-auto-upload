"""Host-only checks for temporary resume and pre-claim update boundaries."""
from pathlib import Path
import os,subprocess,tempfile,unittest
SRC=Path(__file__).resolve().parents[1]/'module'
class MaintenanceTests(unittest.TestCase):
 def test_resume_running_and_stopped_and_busy(self):
  for state in ('running','stopped','busy'):
   with self.subTest(state=state),tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);d=p/'maint';u=p/'u';d.mkdir();u.mkdir();(u/'worker.pid').write_text((str(os.getpid()) if state=='running' else '99999999')+'\n')
    shim=p/'bb';shim.write_text('#!/bin/sh\nexec "$@"\n');shim.chmod(0o700)
    supervisor=p/'supervisor';supervisor.write_text(f'#!/bin/sh\necho {os.getpid()} > "{u}/worker.pid"\necho started > "{d}/started"\nsleep 2\n')
    if state=='busy':(u/'source.fifo').touch()
    s=(SRC/'ablation_resume.sh').read_text().replace('B=/bin/busybox',f'B={shim}').replace('D=/setting/a7c-debug/ram/maint',f'D={d}').replace('U=/setting/a7c-uploader/ram',f'U={u}').replace('/setting/a7c-display/enabled',str(p/'disabled')).replace('/bin/ash /setting/a7c-uploader/supervisor.sh',f'/bin/sh {supervisor}')
    f=p/'resume';f.write_text(s)
    out=subprocess.run(['sh',str(f)],capture_output=True,text=True,timeout=5)
    self.assertEqual(out.returncode,94 if state=='busy' else 0,out.stdout+out.stderr)
    self.assertEqual((d/'started').exists(),state=='stopped')
 def test_updates_only_before_claim_and_no_rearm(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);d=p/'maint';d.mkdir();shim=p/'bb';shim.write_text('#!/bin/sh\nexec "$@"\n');shim.chmod(0o700)
   f=p/'manage';f.write_text((SRC/'ablation_manage.sh').read_text().replace('B=/bin/busybox',f'B={shim}').replace('D=/setting/a7c-debug/ram/maint',f'D={d}').replace('/bin/ash -n','/bin/sh -n'))
   def call(*args):return subprocess.run(['sh',str(f),*args],capture_output=True,text=True).returncode
   self.assertEqual(call('XLOCK'),0);(d/'incoming').write_text('#!/bin/sh\nexit 0\n')
   self.assertEqual(call('XCOMMIT','action:17:'+'a'*64),0);self.assertTrue((d/'trial.sh').exists());self.assertFalse((d/'incoming').exists())
   self.assertEqual(call('XUNLOCK'),0);(d/'trial.claim').mkdir()
   self.assertNotEqual(call('XLOCK'),0);self.assertNotEqual(call('XIDLE'),0)
   self.assertEqual(call('XREARM'),64);self.assertEqual(call('XREADLOCK'),0);self.assertEqual(call('XUNLOCK'),0)
   self.assertTrue((d/'trial.claim').exists())
if __name__=='__main__':unittest.main()

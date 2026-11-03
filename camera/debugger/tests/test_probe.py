import pathlib, tempfile, subprocess, unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class ProbeTests(unittest.TestCase):
 def test_probe_idle_only_fixed_command_and_exit_status(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);d=p/'debug';r=p/'runtime';u=p/'upload'
   for x in (d,r,u):x.mkdir()
   bb=p/'bb';bb.write_text('#!/bin/sh\nexec "$@"\n');bb.chmod(0o700)
   probe=d/'probe';probe.write_text('#!/bin/sh\necho "$@" > "'+str(p/'called')+'"\necho state\necho diagnostic >&2\nexit 124\n');probe.chmod(0o700)
   s=SRC.joinpath('action.sh').read_text().replace('B=/bin/busybox','B='+str(bb)).replace('D=/setting/a7c-debug/ram','D='+str(d)).replace('R=/setting/a7c-uploader/ram','R='+str(r)).replace('U=/setting/a7c-uploader','U='+str(u))
   script=p/'action';script.write_text(s)
   def run():return subprocess.run(['sh',str(script),'PROBE'],capture_output=True,timeout=5)
   (r/'source.fifo').touch();self.assertEqual(run().returncode,2);(r/'source.fifo').unlink();self.assertFalse((p/'called').exists())
   for guard in ('lock','supervisor.lock'):
    (r/guard).mkdir();self.assertEqual(run().returncode,2);(r/guard).rmdir();self.assertFalse((p/'called').exists())
   (r/'lease.ready').touch();self.assertEqual(run().returncode,2);(r/'lease.ready').unlink()
   self.assertEqual(run().returncode,124);self.assertEqual((p/'called').read_text(),'full-info\n')
   self.assertEqual((d/'probe.rc').read_text(),'124\n');self.assertEqual((d/'full-info.txt').read_text(),'state\n')
   self.assertFalse((r/'stop').exists())
 def test_supervisor_ignores_exhausted_budget_and_obeys_enabled_and_lock(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);d=p/'ram';u=p/'setting';d.mkdir();u.mkdir()
   bb=p/'bb';bb.write_text('#!/bin/sh\nexec "$@"\n');bb.chmod(0o700)
   mounts=p/'mounts';mounts.write_text('a7c-debug-ram '+str(d)+' tmpfs rw 0 0\n')
   (u/'budget').write_text('0\n');(u/'enabled').touch()
   for name in ('listener','lease','net','probe'):(u/name).write_text('#!/bin/sh\necho '+name+' >> "'+str(p/'calls')+'"\n')
   script=p/'supervisor';script.write_text(SRC.joinpath('supervisor.sh').read_text().replace('B=/bin/busybox','B='+str(bb)).replace('P=/setting/a7c-debug','P='+str(u)).replace('D=/setting/a7c-debug/ram','D='+str(d)).replace('/proc/mounts',str(mounts)))
   def run():return subprocess.run(['sh',str(script)],capture_output=True,timeout=5)
   self.assertEqual(run().returncode,0);self.assertEqual((p/'calls').read_text(),'listener\n');self.assertTrue((u/'enabled').exists());self.assertEqual((u/'budget').read_text(),'0\n')
   (d/'lock').mkdir();self.assertEqual(run().returncode,90);(d/'lock').rmdir()
   (u/'enabled').unlink();self.assertEqual(run().returncode,90);self.assertEqual((p/'calls').read_text(),'listener\n')
   (u/'enabled').touch();(u/'trial-starts').write_text('2\n')
   self.assertEqual(run().returncode,0);self.assertEqual((u/'trial-starts').read_text(),'1\n')
   self.assertEqual(run().returncode,0);self.assertEqual((u/'trial-starts').read_text(),'0\n')
   self.assertEqual(run().returncode,91);self.assertFalse((u/'enabled').exists());self.assertFalse((d/'lock').exists())
   self.assertEqual((p/'calls').read_text(),'listener\n'*3)
   self.assertIn('trial-exhausted',(u/'last-session.txt').read_text())
 def test_runtime_refuses_wrong_mount_and_mount_failure_without_nand_fallback(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);d=p/'ram';u=p/'setting';d.mkdir();u.mkdir()
   (u/'enabled').touch()
   mounts=p/'mounts';calls=p/'mount-calls'
   bb=p/'bb';bb.write_text('#!/bin/sh\nif [ "$1" = mount ]; then echo "$@" >> "'+str(calls)+'"; exit 77; fi\nexec "$@"\n');bb.chmod(0o700)
   source=SRC.joinpath('supervisor.sh').read_text().replace('B=/bin/busybox','B='+str(bb)).replace('P=/setting/a7c-debug','P='+str(u)).replace('D=/setting/a7c-debug/ram','D='+str(d)).replace('/proc/mounts',str(mounts))
   script=p/'supervisor';script.write_text(source)
   def run():return subprocess.run(['sh',str(script)],capture_output=True,timeout=5)
   mounts.write_text('unexpected '+str(d)+' vfat rw 0 0\n')
   self.assertEqual(run().returncode,90);self.assertFalse(calls.exists());self.assertEqual(list(d.iterdir()),[])
   mounts.write_text('')
   (d/'unexpected-file').touch();self.assertEqual(run().returncode,90);self.assertFalse(calls.exists());(d/'unexpected-file').unlink()
   self.assertEqual(run().returncode,90);self.assertIn('mount -n -t tmpfs',calls.read_text());self.assertEqual(list(d.iterdir()),[])
if __name__=='__main__':unittest.main()

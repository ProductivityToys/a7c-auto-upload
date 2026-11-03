import pathlib,tempfile,subprocess,hashlib,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]/'action.sh'
class ActionTests(unittest.TestCase):
 def test_pause_never_writes_unmounted_runtime_and_start_defers_to_supervisor(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);d=p/'debug';r=p/'runtime';u=p/'upload'
   for x in (d,r,u):x.mkdir()
   mounts=p/'mounts';mounts.write_text('');(u/'enabled').touch()
   bb=p/'bb';bb.write_text('#!/bin/sh\nexec "$@"\n');bb.chmod(0o700)
   source=SRC.read_text().replace('B=/bin/busybox','B='+str(bb)).replace('D=/setting/a7c-debug/ram','D='+str(d)).replace('R=/setting/a7c-uploader/ram','R='+str(r)).replace('U=/setting/a7c-uploader','U='+str(u)).replace('/proc/mounts',str(mounts)).replace('/bin/ash','/bin/sh')
   script=p/'action';script.write_text(source)
   (u/'supervisor.sh').write_text('printf "%s\\n" "$1" > "'+str(p/'started')+'"\n')
   def run(action):return subprocess.run(['sh',str(script),action],capture_output=True,timeout=3)
   self.assertEqual(run('PAUSE').returncode,0);self.assertEqual(list(r.iterdir()),[])
   mounts.write_text('other '+str(r)+' tmpfs rw 0 0\n')
   self.assertEqual(run('PAUSE').returncode,4);self.assertEqual(run('START').returncode,2)
   self.assertEqual(list(r.iterdir()),[]);self.assertFalse((p/'started').exists())
   mounts.write_text('a7c-upload-ram '+str(r)+' tmpfs rw 0 0\n')
   self.assertEqual(run('PAUSE').returncode,0);self.assertTrue((r/'stop').exists())
   self.assertEqual(run('START').returncode,0)
   import time
   for _ in range(50):
    if (p/'started').exists():break
    time.sleep(.01)
   self.assertEqual((p/'started').read_text(),'--start\n')
   self.assertTrue((r/'stop').exists(), 'Only guarded supervisor may clear stop')

 def test_update_requires_idle_hash_and_valid_shell(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);d=p/'debug';r=p/'runtime';u=p/'upload'
   for x in (d,r,u):x.mkdir()
   bb=p/'bb';bb.write_text('#!/bin/sh\ncase "$1" in sha256sum) shift; exec shasum -a 256 "$@";; *) exec "$@";; esac\n');bb.chmod(0o700)
   net=d/'net';net.write_text('#!/bin/sh\ncp "'+str(p/'artifact')+'" "$3"\n');net.chmod(0o700)
   source=SRC.read_text().replace('B=/bin/busybox','B='+str(bb)).replace('D=/setting/a7c-debug/ram','D='+str(d)).replace('R=/setting/a7c-uploader/ram','R='+str(r)).replace('U=/setting/a7c-uploader','U='+str(u)).replace('/bin/ash','/bin/sh')
   script=p/'action.sh';script.write_text(source);old=b'#!/bin/sh\necho old\n';(u/'worker.sh').write_bytes(old)
   good=b'#!/bin/sh\necho new\n';(p/'artifact').write_bytes(good);sha=hashlib.sha256(good).hexdigest()
   def run(h):return subprocess.run(['sh',str(script),'UPDATE',h],capture_output=True,timeout=5)
   (r/'lock').mkdir();self.assertEqual(run(sha).returncode,2);(r/'lock').rmdir()
   self.assertEqual(run('0'*64).returncode,7);self.assertEqual((u/'worker.sh').read_bytes(),old)
   bad=b'if then\n';(p/'artifact').write_bytes(bad);self.assertEqual(run(hashlib.sha256(bad).hexdigest()).returncode,8)
   self.assertEqual((u/'worker.sh').read_bytes(),old)
   (p/'artifact').write_bytes(good);self.assertEqual(run(sha).returncode,0)
   self.assertEqual((u/'worker.sh').read_bytes(),good);self.assertEqual((u/'worker.previous.sh').read_bytes(),old)

class TraceTests(unittest.TestCase):
 def test_trace_reads_fixed_logs_while_busy_without_touching_fifo(self):
  import os
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);d=p/'debug';r=p/'runtime';u=p/'upload'
   for x in (d,r,u):x.mkdir()
   bb=p/'bb';bb.write_text('#!/bin/sh\ncase "$1" in head|awk) echo "applet not found" >&2; exit 127;; esac\nexec "$@"\n');bb.chmod(0o700)
   (r/'lock').mkdir();os.mkfifo(r/'source.fifo')
   (r/'copy.log').write_text('MONITOR rc=76 submitted=0\n'+'x'*5000+'END_OF_LOG')
   (u/'token').write_text('not-for-output')
   s=SRC.read_text().replace('B=/bin/busybox','B='+str(bb)).replace('D=/setting/a7c-debug/ram','D='+str(d)).replace('R=/setting/a7c-uploader/ram','R='+str(r)).replace('U=/setting/a7c-uploader','U='+str(u))
   script=p/'action';script.write_text(s)
   run=subprocess.run(['sh',str(script),'TRACE'],capture_output=True,text=True,timeout=3)
   self.assertEqual(run.returncode,0);self.assertIn('MONITOR rc=76 submitted=0',run.stdout);self.assertIn('END_OF_LOG',run.stdout);self.assertIn('TRUNCATED=1',run.stdout)
   self.assertTrue(run.stdout.rstrip().endswith('A7C_DEBUG_END'));self.assertLess(len(run.stdout),32768);self.assertNotIn('not-for-output',run.stdout)
   self.assertTrue((r/'lock').exists());self.assertTrue((r/'source.fifo').is_fifo())
   (r/'plain-worker.sh').touch()
   for name in ('plain.worker.pid plain.stdout plain-ftp.log receipt.err receipt-copy.log receipt.root plain-stage.log copy.log relay.log relay.result copy.done guard.done relay.ready lease.log scan-lease.log events.log').split():
    (r/name).write_text(name+'\n'+'x'*5000+'END_'+name)
   (r/'plain-password.fifo').write_text('secret-not-for-output')
   run=subprocess.run(['sh',str(script),'TRACE'],capture_output=True,text=True,timeout=3)
   self.assertEqual(run.returncode,0);self.assertIn('END_receipt-copy.log',run.stdout)
   self.assertTrue(run.stdout.rstrip().endswith('A7C_DEBUG_END'));self.assertLess(len(run.stdout),32768)
   self.assertNotIn('secret-not-for-output',run.stdout)

if __name__=='__main__':unittest.main()

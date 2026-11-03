"""Completed FIFO paths may be unlinked; uncertain native readers must survive."""
import os,pathlib,subprocess,tempfile,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class CleanupTests(unittest.TestCase):
 def test_real_transfer_children_finish_before_fifo_removal(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   subprocess.run(['cc','-O2',str(SRC/'relay.c'),'-o',str(d/'relay')],check=True)
   def exe(name,body):
    p=d/name;p.write_text('#!/bin/sh\n'+body);p.chmod(0o700);return p
   bb=exe('bb','exec "$@"\n')
   exe('monitor','printf video > "$TEST_DIR/source.fifo"\n')
   exe('net','cat "$TEST_DIR/network.fifo" > "$TEST_DIR/received"\necho done > "$TEST_DIR/network-exited"\n')
   source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
   source=source.replace('B=/bin/busybox',f'B={bb}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
   source+='''
checkpoint() { :; }
report() { :; }
put() {
 if [ "$2" = "commit-$ATTEMPT.txt" ]; then
  [ -f "$D/network-exited" ] && [ -f "$D/guard.done" ] &&
  [ ! -e "$D/source.fifo" ] && [ ! -e "$D/network.fifo" ] || return 98
 fi
}
plan() { echo "DONE $ATTEMPT" > "$D/plan"; }
SIZE=5; LIMIT=10; DRIVE=A; VIDEO=C0001.MP4; ATTEMPT=aaaaaaaaaaaaaaaaaaaaaaaa
transfer
exit $?
'''
   script=d/'test.sh';script.write_text(source)
   p=subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_DIR=str(d)),capture_output=True,timeout=15)
   self.assertEqual(p.returncode,0,p.stderr.decode())
   self.assertEqual((d/'received').read_bytes(),b'video')
   self.assertFalse((d/'source.fifo').exists());self.assertFalse((d/'network.fifo').exists())
   self.assertIn('DONE C0001.MP4',(d/'events.log').read_text())

 def test_unsubmitted_copy_drains_empty_readers_and_allows_retry(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   subprocess.run(['cc','-O2',str(SRC/'relay.c'),'-o',str(d/'relay')],check=True)
   def exe(name,body):
    p=d/name;p.write_text('#!/bin/sh\n'+body);p.chmod(0o700);return p
   bb=exe('bb','exec "$@"\n')
   exe('monitor','exit 76\n')
   exe('net','cat "$TEST_DIR/network.fifo" > "$TEST_DIR/received"\necho done > "$TEST_DIR/network-exited"\n')
   source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
   source=source.replace('B=/bin/busybox',f'B={bb}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
   source+='''
checkpoint() { :; }
report() { :; }
put() {
 if [ "$2" = "commit-$ATTEMPT.txt" ]; then
  [ -f "$D/network-exited" ] && [ -f "$D/guard.done" ] &&
  [ ! -e "$D/source.fifo" ] && [ ! -e "$D/network.fifo" ] || return 98
 fi
}
plan() { echo "DONE $ATTEMPT" > "$D/plan"; }
SIZE=5; LIMIT=10; DRIVE=A; VIDEO=C0001.MP4; ATTEMPT=aaaaaaaaaaaaaaaaaaaaaaaa
transfer
exit $?
'''
   script=d/'test.sh';script.write_text(source)
   p=subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_DIR=str(d)),capture_output=True,timeout=15)
   self.assertEqual(p.returncode,1,p.stderr.decode())
   self.assertEqual((d/'received').read_bytes(),b'')
   self.assertEqual((d/'guard.done').read_text(),'normal\n')
   self.assertFalse((d/'source.fifo').exists());self.assertFalse((d/'network.fifo').exists())
   self.assertFalse((d/'commit.txt').exists())

 def test_native_completion_and_guardian_are_both_required(self):
  cases=[(0,True,'normal',True),(73,True,'recovered',True),(76,True,'normal',True),
         (124,True,'normal',False),(0,False,'normal',False),
         (0,True,None,False),(0,True,'unknown',False)]
  for rc,done,guard,expected in cases:
   with self.subTest(rc=rc,done=done,guard=guard),tempfile.TemporaryDirectory() as tmp:
    d=pathlib.Path(tmp)
    for name in ('source.fifo','network.fifo'):os.mkfifo(d/name)
    if done:(d/'copy.done').touch()
    if guard is not None:(d/'guard.done').write_text(guard+'\n')
    bb=d/'bb';bb.write_text('#!/bin/sh\nexec "$@"\n');bb.chmod(0o700)
    source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
    source=source.replace('B=/bin/busybox',f'B={bb}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
    source+=f'\ncopy_rc={rc}\ncleanup_completed_fifos\n'
    script=d/'test.sh';script.write_text(source)
    p=subprocess.run(['sh',str(script)],capture_output=True,timeout=3)
    self.assertEqual(p.returncode,0 if expected else 1,p.stderr.decode())
    for name in ('source.fifo','network.fifo'):self.assertEqual((d/name).exists(),not expected)
    self.assertEqual((d/'copy.done').exists(),done)
    self.assertEqual((d/'guard.done').exists(),guard is not None)
if __name__=='__main__':unittest.main()

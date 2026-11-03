"""Private runtime bootstrap: no files are written before tmpfs is verified."""
import os, pathlib, subprocess, tempfile, unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class RuntimeTests(unittest.TestCase):
 def test_mount_ownership_failure_and_success(self):
  with tempfile.TemporaryDirectory() as temp:
   t=pathlib.Path(temp);p=t/'setting';d=p/'ram';d.mkdir(parents=True)
   mounts=t/'mounts';mounts.write_text('');(p/'enabled').touch()
   worker=p/'worker.sh';worker.write_text('echo started >> "'+str(t/'starts')+'"\nexit 42\n')
   bb=t/'bb';bb.write_text('''#!/bin/sh
if [ "$1" = mount ]; then
 echo "$@" >> "$TEST_ROOT/mount-calls"
 [ "$MOUNT_OK" = 1 ] || exit 77
 echo "a7c-upload-ram $TEST_ROOT/setting/ram tmpfs rw 0 0" > "$TEST_ROOT/mounts"
 exit 0
fi
exec "$@"
''');bb.chmod(0o700)
   source=(SRC/'supervisor.sh').read_text().replace('B=/bin/busybox','B='+str(bb)).replace('P=/setting/a7c-uploader','P='+str(p)).replace('D=/setting/a7c-uploader/ram','D='+str(d)).replace('/proc/mounts',str(mounts)).replace('/bin/ash','/bin/sh')
   script=t/'supervisor';script.write_text(source)
   def run(ok='0'):
    return subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_ROOT=str(t),MOUNT_OK=ok),capture_output=True,timeout=4)
   self.assertEqual(run().returncode,90);self.assertFalse((t/'starts').exists());self.assertEqual(list(d.iterdir()),[])
   (t/'mount-calls').unlink();mounts.write_text('unknown '+str(d)+' vfat rw 0 0\n')
   self.assertEqual(run('1').returncode,90);self.assertFalse((t/'mount-calls').exists())
   mounts.write_text('');(d/'unexpected').touch()
   self.assertEqual(run('1').returncode,90);self.assertFalse((t/'mount-calls').exists());(d/'unexpected').unlink()
   result=run('1');self.assertEqual(result.returncode,0,result.stderr.decode())
   self.assertEqual((t/'starts').read_text(),'started\n');self.assertEqual((d/'worker.exit').read_text(),'42\n')
   self.assertIn('size=2048k,mode=0700,nosuid,nodev',(t/'mount-calls').read_text());self.assertFalse((d/'supervisor.lock').exists())
   (d/'stop').touch()
   result=subprocess.run(['sh',str(script),'--start'],env=dict(os.environ,TEST_ROOT=str(t),MOUNT_OK='1'),capture_output=True,timeout=4)
   self.assertEqual(result.returncode,0,result.stderr.decode());self.assertFalse((d/'stop').exists())
   self.assertEqual((t/'starts').read_text(),'started\nstarted\n')
if __name__=='__main__':unittest.main()

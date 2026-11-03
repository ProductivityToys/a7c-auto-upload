"""A real frontend dying before vs after submission must produce distinct results."""
import os,pathlib,subprocess,tempfile,unittest,time
SRC=pathlib.Path(__file__).resolve().parents[1]
class MonitorProcessTests(unittest.TestCase):
 def test_submission_boundary_and_native_success(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);frontend=d/'frontend'
   frontend.write_text('''#!/usr/bin/env python3
import os,signal,time
mode=os.environ['MODE']
os.read(0,1)
if mode=='kill_before':os.kill(os.getpid(),signal.SIGKILL)
if mode=='exit_before':raise SystemExit(3)
os.write(1,b'Logical  Addr\\n')
cmd=b''
while True:
 x=os.read(0,1)
 if not x:raise SystemExit(4)
 if x==b'\\r':break
 cmd+=x
open(os.environ['COMMAND'],'wb').write(cmd)
if mode=='kill_after':os.kill(os.getpid(),signal.SIGKILL)
if mode=='hang_after':time.sleep(20)
os.write(1,cmd+b'\\r\\nMWF>')
time.sleep(2)
''');frontend.chmod(0o700)
   binary=d/'monitor'
   subprocess.run(['cc','-fno-builtin','-DA7C_MONOTONIC_CLOCK='+str(time.CLOCK_MONOTONIC),'-DA7C_TEST_FRONTEND="'+str(frontend)+'"',str(SRC/'monitor.c'),'-o',str(binary)],check=True)
   for mode,rc,submitted in [('kill_before',76,False),('exit_before',76,False),('kill_after',72,True),('hang_after',124,True),('success',0,True)]:
    with self.subTest(mode=mode):
     command=d/'command'
     if command.exists():command.unlink()
     p=subprocess.run([str(binary),'copy','A','C0001.MP4','10'],env=dict(os.environ,MODE=mode,COMMAND=str(command)),capture_output=True,timeout=16)
     self.assertEqual(p.returncode,rc,p.stderr.decode());self.assertEqual(command.exists(),submitted)
     if rc:self.assertIn('submitted='+str(int(submitted)),p.stderr.decode())
if __name__=='__main__':unittest.main()

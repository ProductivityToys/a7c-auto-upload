import os,pathlib,signal,subprocess,tempfile,time,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class NetTests(unittest.TestCase):
 def test_timeout_and_cancel_reap_ftp(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);token=d/'token';token.write_text('a'*64+'\n');bb=d/'fake-busybox';pidfile=d/'pid'
   bb.write_text('#!/bin/sh\necho $$ > "$NET_TEST_PID"\ntrap "" TERM\nexec sleep 30\n');bb.chmod(0o700);exe=d/'net'
   subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-DBB_EXEC="'+str(bb)+'"','-DTOKEN_FILE="'+str(token)+'"',str(SRC/'net.c'),'-o',str(exe)],check=True)
   env=dict(os.environ,NET_TEST_PID=str(pidfile))
   for cancel in (False,True):
    pidfile.unlink(missing_ok=True);p=subprocess.Popen([str(exe),'put','status.txt','unused','1' if not cancel else '30'],env=env)
    end=time.monotonic()+3
    while not pidfile.exists() and time.monotonic()<end:time.sleep(.01)
    self.assertTrue(pidfile.exists());child=int(pidfile.read_text())
    if cancel:p.terminate()
    self.assertEqual(p.wait(timeout=5),143 if cancel else 124)
    with self.assertRaises(ProcessLookupError):os.kill(child,0)
if __name__=='__main__':unittest.main()

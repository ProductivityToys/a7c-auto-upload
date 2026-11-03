"""Portable tests of FIFO backpressure, SHA and guardian recovery; no camera."""
import hashlib, os, pathlib, subprocess, tempfile, threading, time, unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class Relay(unittest.TestCase):
 size_only=False
 @classmethod
 def setUpClass(cls):
  cls.build=tempfile.TemporaryDirectory();cls.binary=pathlib.Path(cls.build.name)/'relay'
  subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror',*(['-DRELAY_SIZE_ONLY'] if cls.size_only else []),str(SRC/'relay.c'),'-o',str(cls.binary)],check=True)
 @classmethod
 def tearDownClass(cls):cls.build.cleanup()
 def exercise(self,blocks,mode='normal'):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);os.mkfifo(d/'source.fifo');os.mkfifo(d/'network.fifo');block=bytes(range(256))*4096;size=len(block)*blocks
   received=hashlib.sha256();source=hashlib.sha256();errors=[];written=[0]
   def reader():
    try:
     with (d/'network.fifo').open('rb',buffering=0) as f:
      while True:
       b=f.read(65536)
       if not b:break
       received.update(b)
       if mode=='broken':break
    except Exception as e:errors.append(e)
   thread=threading.Thread(target=reader);thread.start();p=subprocess.Popen([str(self.binary),str(d),str(size)])
   end=time.monotonic()+12
   while not (d/'relay.ready').exists() and p.poll() is None and time.monotonic()<end:time.sleep(.01)
   self.assertTrue((d/'relay.ready').exists())
   def writer():
    try:
     with (d/'source.fifo').open('wb',buffering=0) as f:
      for _ in range(blocks):

       # PIPE_BUF-sized writes avoid Darwin large-FIFO-write stalls when
       # the no-hash relay drains much faster; still exercise backpressure.
       for offset in range(0,len(block),4096):
        chunk=block[offset:offset+4096];n=f.write(chunk);self.assertEqual(n,len(chunk));written[0]+=n;source.update(chunk)
     (d/'copy.done').write_text('0\n')
    except Exception as e:errors.append(e)
   w=threading.Thread(target=writer);w.start()
   if mode=='kill':time.sleep(.01);p.kill()
   w.join(100);thread.join(10);self.assertFalse(w.is_alive());self.assertFalse(thread.is_alive());rc=p.wait(timeout=10)
   end=time.monotonic()+5
   while not (d/'guard.done').exists() and time.monotonic()<end:time.sleep(.01)
   self.assertTrue((d/'guard.done').exists());self.assertFalse(errors);self.assertEqual(written[0],size)
   if mode=='kill':self.assertEqual((d/'guard.done').read_text(),'recovered\n')
   else:
    fields=(d/'relay.result').read_text().split()
    self.assertEqual(len(fields),2 if self.size_only else 3)
    failed,total=fields[:2];self.assertEqual(int(total),size)
    if not self.size_only:self.assertEqual(fields[2],source.hexdigest())
    if mode=='normal':self.assertEqual(rc,0);self.assertEqual(failed,'0');self.assertEqual(source.hexdigest(),received.hexdigest())
    else:self.assertNotEqual(rc,0);self.assertEqual(failed,'1')
 def test_normal(self):self.exercise(4)
 def test_broken_network_drains(self):self.exercise(4,'broken')
 def test_relay_killed_guard_drains(self):self.exercise(8,'kill')
 @unittest.skipUnless(os.getenv('A7C_LARGE_TEST'),'Explicit >4 GiB streaming test')
 def test_counter_over_4gib(self):self.exercise(4097)
class SizeOnlyRelay(Relay):
 size_only=True
if __name__=='__main__':unittest.main()

"""Integration tests of the actual C client against ordinary pyftpdlib FTP.
Run in the research venv (pyftpdlib 2.2.0); no NAS/camera/credentials involved.
"""
import hashlib, logging, pathlib, subprocess, tempfile, threading, time, unittest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.ioloop import IOLoop
from pyftpdlib.log import config_logging
config_logging(level=logging.CRITICAL)

SRC=pathlib.Path(__file__).resolve().parents[1]
logging.getLogger('pyftpdlib').setLevel(logging.CRITICAL)
class FTPTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.build=tempfile.TemporaryDirectory();cls.tool=pathlib.Path(cls.build.name)/'ftp'
  cls.progress=pathlib.Path(cls.build.name)/'progress';cls.progress.mkdir()
  subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-DA7C_PROGRESS_RAM="'+str(cls.progress)+'/"',
                  str(SRC/'ftp.c'),str(SRC.parent/'receipt/receipt.c'),'-o',str(cls.tool)],check=True)
 @classmethod
 def tearDownClass(cls):cls.build.cleanup()
 def setUp(self):
  for x in self.progress.iterdir():x.unlink()
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.remote=self.root/'remote';self.remote.mkdir()
  self.ops=[];self.fault=None;owner=self
  auth=DummyAuthorizer();auth.add_user('test','only-test-secret',str(self.remote),perm='elradfmwMT')
  class Handler(FTPHandler):
   authorizer=auth
   def ftp_STOR(self,file,mode='w'):
    owner.ops.append('STOR');self.uploading=True;return super().ftp_STOR(file,mode)
   def ftp_RETR(self,file):
    owner.ops.append('RETR');raise AssertionError('video readback forbidden')
   def ftp_SIZE(self,path):
    if owner.fault=='deny_size' and path.endswith('.MP4'):return self.respond('550 Not permitted')
    return super().ftp_SIZE(path)
   def ftp_NOOP(self,line):
    if owner.fault=='slow_noop':time.sleep(1.7)
    return super().ftp_NOOP(line)
   def on_file_received(self,path):
    if owner.fault=='truncate':pathlib.Path(path).write_bytes(b'short')
   def ftp_RNTO(self,path):
    self.drop_reply=owner.fault=='rename_reply_lost'
    try:return super().ftp_RNTO(path)
    finally:self.drop_reply=False
   def respond(self,resp,*args,**kwargs):
    if owner.fault=='transfer_reply_lost' and getattr(self,'uploading',False) and resp.startswith('226'):
     self.close();return
    if getattr(self,'drop_reply',False) and resp.startswith('250'):
     self.close();return
    return super().respond(resp,*args,**kwargs)
  self.loop=IOLoop();self.server=FTPServer(('127.0.0.1',0),Handler,ioloop=self.loop);self.port=self.server.socket.getsockname()[1]
  self.stopping=threading.Event()
  def serve():
   while not self.stopping.is_set():self.loop.loop(timeout=.01,blocking=False)
   self.server.close_all()
  self.thread=threading.Thread(target=serve,daemon=True);self.thread.start()
  self.content=bytes(range(256))*4096;self.source=self.root/'source';self.source.write_bytes(self.content)
  self.identity=hashlib.sha256(b'clip-identity').hexdigest();self.sha=hashlib.sha256(self.content).hexdigest()
 def tearDown(self):
  self.stopping.set();self.thread.join(2);self.assertFalse(self.thread.is_alive());self.tmp.cleanup()
 def call(self,action,last,secret=b'only-test-secret\n'):
  return subprocess.run([str(self.tool),action,'127.0.0.1',str(self.port),'test','/',self.identity,str(len(self.content)),str(last),'8'],input=secret,capture_output=True,timeout=12)
 def put(self):return self.call('put',self.source)
 def commit(self):return self.call('commit','-')
 def check(self,secret=b'only-test-secret\n',directory='/',fast=False):
  return subprocess.run([str(self.tool),'check-fast' if fast else 'check','127.0.0.1',str(self.port),'test',directory],input=secret,capture_output=True,timeout=6)
 def test_fast_recovery_check_is_bounded_but_normal_check_accepts_slow_reply(self):
  self.fault='slow_noop';started=time.monotonic();p=self.check(fast=True)
  self.assertEqual(p.returncode,75,p.stderr);self.assertLess(time.monotonic()-started,1.8)
  self.assertEqual(self.check().returncode,0)
  self.assertEqual(self.ops,[])
 def test_health_check_logs_in_and_enters_directory_without_media_io(self):
  p=self.check();self.assertEqual(p.returncode,0,p.stderr);self.assertFalse(p.stdout);self.assertFalse(self.ops)
  self.assertEqual(list(self.remote.iterdir()),[])
 def test_health_check_rejects_authentication_or_missing_directory(self):
  self.assertEqual(self.check(b'wrong\n').returncode,75)
  self.assertEqual(self.check(directory='/missing').returncode,75)
  self.assertFalse(self.ops);self.assertEqual(list(self.remote.iterdir()),[])
 def test_progress_is_request_bound_capped_and_does_not_commit(self):
  token='123 456 7 240\n';(self.progress/'display.active').write_text(token)
  self.assertEqual(self.put().returncode,0)
  self.assertEqual((self.progress/'display.progress').read_text(),token+'99\n')
  self.assertFalse((self.remote/(self.identity+'.MP4')).exists())
  self.assertEqual(self.commit().returncode,0)
  self.assertEqual((self.progress/'display.progress').read_text(),token+'99\n')
 def test_progress_output_failure_never_fails_ftp(self):
  (self.progress/'display.active').write_text('123 456 7 240\n')
  (self.progress/'display.progress').mkdir()
  try:
   self.assertEqual(self.put().returncode,0)
   self.assertEqual(self.commit().returncode,0)
  finally:(self.progress/'display.progress').rmdir()
 def test_stream_commit_and_record(self):
  p=self.put();self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout,b'');self.assertFalse((self.remote/(self.identity+'.MP4')).exists())
  c=self.commit();self.assertEqual(c.returncode,0,c.stderr);self.assertEqual(len(c.stdout),512)
  self.assertEqual(c.stdout[9],1);self.assertEqual(c.stdout[88:120],b'\0'*32);self.assertEqual(c.stdout[480:],hashlib.sha256(c.stdout[:480]).digest())
  self.assertEqual((self.remote/(self.identity+'.MP4')).read_bytes(),self.content)
 def test_slot_is_bound_to_destination_and_full_identity(self):
  args=[str(self.tool),'slot','127.0.0.1',str(self.port),'test','/',self.identity]
  def run(a):return subprocess.run(a,capture_output=True,timeout=3)
  first=run(args);self.assertEqual(first.returncode,0);self.assertRegex(first.stdout.decode(),r'^[0-9A-F]{6}\n$');self.assertEqual(run(args).stdout,first.stdout)
  for index,value in [(4,'newuser'),(5,'/other'),(6,'f'*64)]:
   changed=args.copy();changed[index]=value;self.assertNotEqual(run(changed).stdout,first.stdout)
  changed=args.copy();changed[6]='not-an-identity';self.assertEqual(run(changed).returncode,64)
  self.assertEqual(self.ops,[])
 def test_missing_sd_receipt_reconciles_existing_final_without_overwrite(self):
  self.assertEqual(self.put().returncode,0);self.assertEqual(self.commit().returncode,0);count=len(self.ops)
  self.assertEqual(self.put().returncode,0);self.assertEqual(len(self.ops),count)
  self.assertEqual(self.commit().returncode,0)
 def test_lost_rename_response_recovers(self):
  self.assertEqual(self.put().returncode,0);self.fault='rename_reply_lost'
  c=self.commit();self.assertEqual(c.returncode,75);self.assertFalse(c.stdout);self.assertTrue((self.remote/(self.identity+'.MP4')).exists())
  self.fault=None;self.assertEqual(self.commit().returncode,0)
 def test_size_policy_accepts_equal_length_content_without_claiming_hash(self):
  self.assertEqual(self.put().returncode,0);part=self.remote/('.'+self.identity+'.part');part.write_bytes(b'x'*len(self.content))
  c=self.commit();self.assertEqual(c.returncode,0,c.stderr);self.assertEqual(c.stdout[9],1);self.assertEqual(c.stdout[88:120],b'\0'*32)
  self.assertNotIn('RETR',self.ops)
 def test_existing_same_length_final_preserved_without_readback(self):
  final=self.remote/(self.identity+'.MP4');final.write_bytes(b'x'*len(self.content))
  self.assertEqual(self.put().returncode,0);c=self.commit();self.assertEqual(c.returncode,0,c.stderr)
  self.assertEqual(final.read_bytes(),b'x'*len(self.content));self.assertFalse(self.ops)
 def test_short_partial_never_published_or_receipted(self):
  self.assertEqual(self.put().returncode,0);part=self.remote/('.'+self.identity+'.part');part.write_bytes(b'short')
  c=self.commit();self.assertEqual(c.returncode,75);self.assertFalse(c.stdout);self.assertFalse((self.remote/(self.identity+'.MP4')).exists())
  self.assertEqual(self.put().returncode,0);self.assertEqual(self.commit().returncode,0)
 def test_lost_transfer_reply_requires_retry(self):
  self.fault='transfer_reply_lost';p=self.put();self.assertEqual(p.returncode,75);self.assertFalse(p.stdout)
  self.assertFalse((self.remote/(self.identity+'.MP4')).exists())
  self.fault=None;self.assertEqual(self.put().returncode,0);self.assertEqual(self.commit().returncode,0)
 def test_size_receipt_and_previous_strong_receipt_both_dedup(self):
  self.assertEqual(self.put().returncode,0);c=self.commit();self.assertEqual(c.returncode,0)
  args=[str(self.tool),'match','127.0.0.1',str(self.port),'test','/',self.identity,str(len(self.content)),str(self.root/'receipt'),'-']
  r=bytearray(c.stdout)
  for strong in (False,True):
   if strong:r[9]=2;r[88:120]=bytes.fromhex(self.sha);r[480:]=hashlib.sha256(r[:480]).digest()
   (self.root/'receipt').write_bytes(r)
   p=subprocess.run(args,capture_output=True,timeout=3);self.assertEqual(p.returncode,0,p.stderr)
 def test_rekey_preserves_original_remote_evidence_and_row_match_needs_no_xml(self):
  self.assertEqual(self.put().returncode,0);old=self.commit();self.assertEqual(old.returncode,0)
  f=self.root/'receipt';f.write_bytes(old.stdout);newid=hashlib.sha256(b'a7c-file-v1:C0001.MP4:1048576:2026-10-22T17:00:00').hexdigest()
  base=[str(self.tool),'rekey','127.0.0.1',str(self.port),'test','/',self.identity,str(len(self.content)),str(f),'-']
  converted=subprocess.run(base+[newid],capture_output=True,timeout=3);self.assertEqual(converted.returncode,0,converted.stderr)
  self.assertEqual(len(converted.stdout),512);self.assertEqual(converted.stdout[56:88],bytes.fromhex(newid))
  self.assertEqual(converted.stdout[88:480],old.stdout[88:480]);self.assertEqual(converted.stdout[:56],old.stdout[:56]);f.write_bytes(converted.stdout)
  match=[str(self.tool),'match-row',*base[2:6],newid,str(len(self.content)),str(f),'-']
  self.assertEqual(subprocess.run(match,capture_output=True,timeout=3).returncode,0)
  for index,value in [(4,'different-user'),(6,'f'*64),(7,'1')]:
   changed=match.copy();changed[index]=value;self.assertEqual(subprocess.run(changed,capture_output=True,timeout=3).returncode,90)
  corrupt=bytearray(converted.stdout);corrupt[100]^=1;f.write_bytes(corrupt)
  self.assertEqual(subprocess.run(match,capture_output=True,timeout=3).returncode,10)
 def test_rekey_refuses_unproven_old_receipt(self):
  f=self.root/'receipt';f.write_bytes(b'incomplete')
  p=subprocess.run([str(self.tool),'rekey','127.0.0.1',str(self.port),'test','/',self.identity,str(len(self.content)),str(f),'-','f'*64],capture_output=True,timeout=3)
  self.assertEqual(p.returncode,90);self.assertFalse(p.stdout)
 def test_550_does_not_mean_absent(self):
  final=self.remote/(self.identity+'.MP4');final.write_bytes(self.content);self.fault='deny_size'
  self.assertEqual(self.put().returncode,90);self.assertFalse(self.ops);self.assertEqual(final.read_bytes(),self.content)
 def test_authentication_failure_is_retryable_no_write(self):
  p=self.call('put',self.source,b'wrong\n');self.assertEqual(p.returncode,75);self.assertFalse(self.ops)
 def test_truncated_upload_is_not_published(self):
  self.fault='truncate';p=self.put();self.assertEqual(p.returncode,75);self.assertFalse(p.stdout)
  self.assertFalse((self.remote/(self.identity+'.MP4')).exists());self.fault=None
  self.assertEqual(self.put().returncode,0);self.assertEqual(self.commit().returncode,0)
 def test_install_trigger_requires_exact_one_byte(self):
  command=[str(self.tool),'armed','127.0.0.1',str(self.port),'test','/',self.identity]
  def run():return subprocess.run(command,input=b'only-test-secret\n',capture_output=True,timeout=12)
  self.assertEqual(run().returncode,75)
  trigger=self.remote/('.a7c-start-'+self.identity)
  trigger.write_bytes(b'');self.assertEqual(run().returncode,75)
  trigger.write_bytes(b'1');self.assertEqual(run().returncode,0)
  trigger.write_bytes(b'11');self.assertEqual(run().returncode,75)
 def test_wrong_size_existing_final_preserved(self):
  final=self.remote/(self.identity+'.MP4');final.write_bytes(b'keep')
  self.assertEqual(self.put().returncode,90);self.assertEqual(final.read_bytes(),b'keep');self.assertFalse(self.ops)
if __name__=='__main__':unittest.main()

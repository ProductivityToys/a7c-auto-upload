import pathlib,subprocess,tempfile,socket,time,unittest,json
SRC=pathlib.Path(__file__).resolve().parents[1]
class ListenerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.tmp.name);self.r=self.p/'ram';self.r.mkdir();self.t=self.p/'token';self.t.write_text('a'*64+'\n')
  (self.p/'enabled').write_text('a7c-resident-v1\n')
  (self.p/'action.sh').write_text('#!/bin/sh\necho "$1" >> "'+str(self.p/'calls')+'"\nprintf "A7C_DEBUG_V2\\nA7C_DEBUG_END\\n"\n')
  (self.r/'lease').write_text('#!/bin/sh\ntouch "'+str(self.r/'lease.ready')+'"\nwhile [ ! -f "'+str(self.r/'lease.done')+'" ]; do sleep .01; done\n');(self.r/'lease').chmod(0o700)
  with socket.socket() as s:s.bind(('127.0.0.1',0));self.port=s.getsockname()[1]
  flags=['-DROOT="'+str(self.p)+'"','-DRAM="'+str(self.r)+'"','-DTOKEN="'+str(self.t)+'"','-DSHELL="/bin/sh"','-DPEER="127.0.0.1"','-DPORT='+str(self.port)]
  flags.extend(getattr(self,'additional_flags',[]))
  # Observe the real event loop, not a copied implementation. Timed idle polls
  # in the previous listener produce another entry after one second.
  wrapper=self.p/'poll.c';wrapper.write_text('#include <poll.h>\n#include <stdio.h>\nint a7c_test_poll(struct pollfd *p,nfds_t n,int t){ if(n==2 || (n==1 && (t==1000 || t==-1))){FILE *f=fopen('+json.dumps(str(self.p/'idle-polls'))+',"a");if(f){fprintf(f,"%d\\n",t);fclose(f);}}return poll(p,n,t);}\n')
  obj=self.p/'listener.o'
  subprocess.run(['cc','-Wall','-Wextra','-Werror','-Dpoll=a7c_test_poll',*flags,'-c',str(SRC/'listener.c'),'-o',str(obj)],check=True)
  self.bin=self.p/'listener';subprocess.run(['cc',str(obj),str(wrapper),'-o',str(self.bin)],check=True)
  self.proc=subprocess.Popen([str(self.bin)])
  for _ in range(100):
   if (self.r/'listener.pid').exists():break
   time.sleep(.01)
  self.assertIsNone(self.proc.poll())
 def tearDown(self):
  self.proc.terminate();self.proc.wait(timeout=5);self.tmp.cleanup()
 def call(self,action='STATUS',token='a'*64,nonce=None,seq=None,extra=''):
  with socket.create_connection(('127.0.0.1',self.port),timeout=3) as s:
   f=s.makefile('rb');hello=f.readline().decode().split();sid=hello[1];n=int(hello[2])+1
   s.sendall(('AUTH %s %s %s %s%s\n'%(token,nonce or sid,n if seq is None else seq,action,extra)).encode())
   return f.read().decode()
 def test_auth_session_replay_and_unknown_action(self):
  for kwargs in [dict(token='b'*64),dict(nonce='0'*32),dict(seq=0),dict(action='TRACE',extra=' arbitrary'),dict(action='PROBE',extra=' arbitrary'),dict(action='SHELL'),dict(action='START',extra=' arbitrary')]:
   self.assertEqual(self.call(**kwargs),'REJECTED\n')
  self.assertFalse((self.p/'calls').exists())
  self.assertIn('RESULT 1 STATUS 0',self.call())
  self.assertEqual(self.call(seq=1),'REJECTED\n')
 def test_idle_no_lease_and_explicit_hold_release(self):
  self.assertFalse((self.r/'lease.ready').exists())
  self.assertIn('HOLD 0',self.call('HOLD'))
  for _ in range(100):
   if (self.r/'lease.ready').exists():break
   time.sleep(.01)
  self.assertTrue((self.r/'lease.ready').exists())
  self.assertIn('HOLD 1',self.call('HOLD'))
  self.assertIn('RELEASE 0',self.call('RELEASE'))
  self.assertTrue((self.r/'lease.done').exists());self.assertIsNone(self.proc.poll())
  # Lease child exit wakes and reaps through SIGCHLD without an idle timer.
  time.sleep(.1)
  self.assertIn('HOLD 0',self.call('HOLD'))
  self.assertIn('RELEASE 0',self.call('RELEASE'))
 def test_idle_blocks_without_periodic_timer_and_term_exits(self):
  time.sleep(1.25)
  self.assertEqual((self.p/'idle-polls').read_text().splitlines(),['-1'])
  self.assertFalse((self.p/'calls').exists())
  self.proc.terminate();self.assertEqual(self.proc.wait(timeout=2),0)
 def test_disabled_entry_rejects_next_connection_and_exit_is_persistent(self):
  (self.p/'enabled').unlink()
  try:
   with socket.create_connection(('127.0.0.1',self.port),timeout=2):pass
  except (ConnectionResetError,ConnectionRefusedError):
   pass  # Listener may close before connect returns; verify exit and no dispatch below.
  self.assertEqual(self.proc.wait(timeout=2),0)
  self.assertFalse((self.p/'calls').exists())
 def test_exit_stops_idle_listener_and_removes_enabled(self):
  self.assertIn('EXIT 0',self.call('EXIT'))
  self.assertEqual(self.proc.wait(timeout=2),0)
  self.assertFalse((self.p/'enabled').exists())
 def test_fixed_dispatch_and_update_hash(self):
  self.assertIn('TRACE 0',self.call('TRACE'));self.assertIn('PROBE 0',self.call('PROBE'));self.assertIn('START 0',self.call('START'));self.assertIn('PAUSE 0',self.call('PAUSE'))
  self.assertEqual(self.call('UPDATE',extra=' ../bad'),'REJECTED\n')
  self.assertIn('UPDATE 0',self.call('UPDATE',extra=' '+'c'*64))
  self.assertEqual((self.p/'calls').read_text().splitlines(),['TRACE','PROBE','STATUS','START','STATUS','PAUSE','STATUS','UPDATE','STATUS'])
 def test_real_python_client(self):
  import importlib.util
  p=SRC.parents[1]/'nas/debugger/client.py'
  spec=importlib.util.spec_from_file_location('debug_client',p);client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
  for invalid in (0,91,float('nan'),'75'):
   with self.assertRaises(ValueError):client.request('STATUS',response_timeout=invalid)
  j=client.request('STATUS',host='127.0.0.1',port=self.port,token_file=self.t,response_timeout=75)
  self.assertEqual(j['rc'],0);self.assertEqual(j['seq'],1)
  self.assertEqual(j['report'],'A7C_DEBUG_V2\nA7C_DEBUG_END\n')
class MaintenanceListenerTests(ListenerTests):
 additional_flags=['-DMAINTENANCE_SECONDS=30']
 def test_maintenance_exit_keeps_uploader_running(self):
  self.assertIn('EXIT 0',self.call('EXIT'))
  self.assertEqual(self.proc.wait(timeout=2),0)
  self.assertNotIn('PAUSE',(self.p/'calls').read_text().splitlines())
 def test_deadline_signal_releases_lease_without_uploader_action(self):
  import signal
  self.proc.send_signal(signal.SIGALRM)
  self.assertEqual(self.proc.wait(timeout=2),0)
  self.assertTrue((self.r/'lease.done').exists())
  self.assertFalse((self.p/'calls').exists())
class NoExpiryMaintenanceListenerTests(ListenerTests):
 additional_flags=['-DMAINTENANCE_SECONDS=0','-DACTION_TRACE']
 def test_exit_does_not_stop_uploader(self):
  self.assertIn('EXIT 0',self.call('EXIT'))
  self.assertEqual(self.proc.wait(timeout=2),0)
  self.assertNotIn('PAUSE',(self.p/'calls').read_text().splitlines())
if __name__=='__main__':unittest.main()

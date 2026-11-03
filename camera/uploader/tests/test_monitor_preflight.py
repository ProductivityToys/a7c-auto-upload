"""Preflight batches share one frontend, never a reply or partial transaction."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

SRC=Path(__file__).resolve().parents[1]
class PreflightMonitorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
  frontend=cls.root/'frontend'
  frontend.write_text('''#!/usr/bin/env python3
import os,time
mode=os.environ['MODE'];calls=os.environ['COMMANDS']
os.read(0,1);os.write(1,b'Logical  Addr\\nMON>MWF>')
for step in range(3):
 cmd=b''
 while True:
  x=os.read(0,1)
  if not x:raise SystemExit(0)
  if x==b'\\r':break
  cmd+=x
 with open(calls,'ab') as f:f.write(cmd+b'\\n')
 if mode=='die_second' and step==1:raise SystemExit(7)
 prompt=b'MON>' if cmd.startswith(b'MPR') else b'MWF>'
 os.write(1,cmd+b'\\n'+prompt);time.sleep(.02)
 if cmd==b'MPR Debug RecInfo':
  body=b'[MprMcmd][RecInfo] ====='
  if mode=='standby':body+=b'\\r\\n'+b'contentType:Movie(XAVC), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY\\r\\n'*2
 elif cmd==b'MPR Debug Info':body=b'MprIf Debug Information\\r\\nSTATE'
 elif cmd.startswith(b'IFSYS cp '):body=b"Can't open file x" if mode=='copy_error' else b'copy completed'
 elif cmd==b'IFSYS dir B:/':body=b'[IFSYS]a----- 512 date U123456A.RCP'
 else:raise SystemExit(8)
 os.write(1,cmd+b'\\r\\n'+body+b'\\r\\n'+prompt)
''');frontend.chmod(0o700);cls.binary=cls.root/'monitor'
  subprocess.run(['cc','-fno-builtin','-DA7C_MONOTONIC_CLOCK='+str(time.CLOCK_MONOTONIC),'-DA7C_TEST_FRONTEND="'+str(frontend)+'"',str(SRC/'monitor.c'),'-o',str(cls.binary)],check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def run_mode(self,mode,*args):
  calls=self.root/(self._testMethodName+'.calls')
  p=subprocess.run([str(self.binary),*args],env=dict(os.environ,MODE=mode,COMMANDS=str(calls)),capture_output=True,timeout=12)
  return p,calls.read_text().splitlines() if calls.exists() else []
 def test_standby_uses_one_fresh_query(self):
  p,calls=self.run_mode('standby','recording-bundle');self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(calls,['MPR Debug RecInfo']);self.assertIn(b'A7C_REC_PART_0_END',p.stdout);self.assertNotIn(b'PART_1',p.stdout)
 def test_fallback_is_bracketed_by_two_fresh_recorder_queries(self):
  p,calls=self.run_mode('empty','recording-bundle');self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(calls,['MPR Debug RecInfo','MPR Debug Info','MPR Debug RecInfo'])
  for i in range(3):self.assertIn(f'A7C_REC_PART_{i}_END'.encode(),p.stdout)
 def test_incomplete_recorder_bundle_publishes_nothing(self):
  p,calls=self.run_mode('die_second','recording-bundle');self.assertEqual(p.returncode,72);self.assertEqual(p.stdout,b'')
 def test_metadata_and_root_share_one_sequential_session(self):
  p,calls=self.run_mode('ok','prepare','B','C0216M01.XML');self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(calls,['IFSYS cp B:/PRIVATE/M4ROOT/CLIP/C0216M01.XML /setting/a7c-uploader/ram/metadata.xml','IFSYS dir B:/'])
  self.assertIn(b'U123456A.RCP',p.stdout)
 def test_failed_metadata_copy_does_not_submit_root(self):
  p,calls=self.run_mode('copy_error','prepare','B','C0216M01.XML');self.assertEqual(p.returncode,73);self.assertEqual(len(calls),1);self.assertEqual(p.stdout,b'')
 def test_root_failure_does_not_publish_partial_metadata_transaction(self):
  p,calls=self.run_mode('die_second','prepare','B','C0216M01.XML');self.assertEqual(p.returncode,72);self.assertEqual(p.stdout,b'')
 def test_prepare_whitelist_rejects_video_and_paths(self):
  for name in ['C0216.MP4','../C0216M01.XML','C0216M01.XML.extra']:
   p,calls=self.run_mode('ok','prepare','B',name);self.assertEqual(p.returncode,64);self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()

"""Real frontend protocol: batch replies cannot reuse old prompts or partial data."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

SRC=Path(__file__).resolve().parents[1]

class FilesystemMonitorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
  frontend=cls.root/'frontend'
  frontend.write_text('''#!/usr/bin/env python3
import os,time
r=os.environ['COMMANDS'];mode=os.environ['MODE']
os.read(0,1);os.write(1,b'Logical  Addr\\nMWF>')
for step in range(3):
 cmd=b''
 while True:
  x=os.read(0,1)
  if not x:raise SystemExit(4)
  if x==b'\\r':break
  cmd+=x
 with open(r,'ab') as f:f.write(cmd+b'\\n')
 if mode=='die_second' and step==1:raise SystemExit(7)
 # A local LF echo followed by an old prompt is not command completion.
 os.write(1,cmd+b'\\nMWF>');time.sleep(.02)
 if step==0:body=(b"driveLetter = '?'" if mode=='bad_drive' else b"driveLetter = 'B'")
 elif step==1:body=b'[IFSYS]a----- 24 2026-10-22 12:00:00 C0001.MP4'
 else:body=b'******** Fsys - IFSYS'
 if mode=='overflow' and step==1:body=b'x'*262000
 os.write(1,cmd+b'\\r\\n'+body+b'\\r\\nMWF>')
 time.sleep(.02)
time.sleep(2)
''');frontend.chmod(0o700);cls.binary=cls.root/'monitor'
  subprocess.run(['cc','-fno-builtin','-DA7C_MONOTONIC_CLOCK='+str(time.CLOCK_MONOTONIC),'-DA7C_TEST_FRONTEND="'+str(frontend)+'"',str(SRC/'monitor.c'),'-o',str(cls.binary)],check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def run_mode(self,mode):
  calls=self.root/(mode+'.calls')
  p=subprocess.run([str(self.binary),'filesystem'],env=dict(os.environ,MODE=mode,COMMANDS=str(calls)),capture_output=True,timeout=12)
  return p,calls.read_text().splitlines()
 def test_one_session_three_sequential_fresh_replies(self):
  p,calls=self.run_mode('ok');self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(calls,['IFSYS getdriveletter /dev/mmca','IFSYS dir B:/PRIVATE/M4ROOT/CLIP','IFSYS info'])
  self.assertIn(b"driveLetter = 'B'",p.stdout);self.assertIn(b'C0001.MP4',p.stdout);self.assertIn(b'******** Fsys',p.stdout)
 def test_bad_drive_never_submits_directory_or_emits_snapshot(self):
  p,calls=self.run_mode('bad_drive');self.assertNotEqual(p.returncode,0);self.assertEqual(len(calls),1);self.assertEqual(p.stdout,b'')
 def test_incomplete_second_reply_discards_completed_first_reply(self):
  p,calls=self.run_mode('die_second');self.assertEqual(p.returncode,72,p.stderr);self.assertEqual(len(calls),2);self.assertEqual(p.stdout,b'')
 def test_bounded_transcript_overflow_does_not_publish_partial_snapshot(self):
  p,calls=self.run_mode('overflow');self.assertEqual(p.returncode,71,p.stderr);self.assertEqual(len(calls),2);self.assertEqual(p.stdout,b'')

if __name__=='__main__':unittest.main()

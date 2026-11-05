"""The optimized recorder transport retains both validated state gates."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1]
BASE=SRC.parent/'worker.sh'
FIXTURES=SRC.parents[2]/'nas/receiver/tests'
EMPTY='MPR Debug RecInfo\n[MprMcmd][RecInfo] =====\nMON>\n'
STANDBY='MPR Debug RecInfo\n[MprMcmd][RecInfo] =====\n'+(' + line, contentType:Movie(XAVC), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY\n'*2)+'MON>\n'
STILL='MPR Debug RecInfo\n[MprMcmd][RecInfo] =====\n + line[0], contentType:Still(JPG), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY\nMON>\n'
class RecordingBundleTests(unittest.TestCase):
 def check_gate(self,parts,expected,rc=0):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);(d/'bb').write_text('#!/bin/sh\nexec "$@"\n');(d/'bb').chmod(0o700)
   (d/'bundle').write_text(''.join(f'A7C_REC_PART_{i}_BEGIN\n{x}A7C_REC_PART_{i}_END\n' for i,x in enumerate(parts)))
   (d/'monitor').write_text(f'#!/bin/sh\ncat "{d}/bundle"\nexit {rc}\n');(d/'monitor').chmod(0o700)
   funcs=''
   for source,names in [(BASE,['empty_rec','full_state_idle']),(SRC/'worker.sh',['still_rec_standby','recording_idle'])]:
    for name in names:funcs+=re.search(r'^'+name+r'\(\) \{\n.*?^}\n',source.read_text(),re.M|re.S)[0]
   p=subprocess.run(['sh'],input=f'B={d}/bb\nD={d}\n'+funcs+'recording_idle\n',text=True,capture_output=True)
   self.assertEqual(p.returncode,expected,p.stderr)
 def test_standby_fast_path(self):self.check_gate([STANDBY],0)
 def test_still_standby_is_bracketed_around_full_idle_with_active_still_recorder(self):
  full=re.sub(r'(\+-StillRecorder\s*:\s*)none',r'\1active',(FIXTURES/'full-idle.txt').read_text())
  self.check_gate([STILL,full,STILL],0)
 def test_still_active_count_transition_or_inconsistent_full_state_is_rejected(self):
  full=re.sub(r'(\+-StillRecorder\s*:\s*)none',r'\1active',(FIXTURES/'full-idle.txt').read_text())
  for first,last in [(STILL.replace('RecCnt1:0','RecCnt1:1'),STILL),(STILL,STILL.replace('REC_STATE_STANDBY','REC_STATE_RECORDING')),(STILL,EMPTY)]:
   self.check_gate([first,full,last],2)
  self.check_gate([STILL,(FIXTURES/'full-idle.txt').read_text(),STILL],2)
 def test_empty_bracket_full_idle(self):self.check_gate([EMPTY,(FIXTURES/'full-idle.txt').read_text(),EMPTY],0)
 def test_empty_bracket_full_standby(self):self.check_gate([EMPTY,(FIXTURES/'full-standby.txt').read_text(),EMPTY],0)
 def test_running_rejected(self):self.check_gate([EMPTY,(FIXTURES/'full-running.txt').read_text(),EMPTY],2)
 def test_changed_recorder_rejected(self):self.check_gate([EMPTY,(FIXTURES/'full-idle.txt').read_text(),STANDBY],2)
 def test_missing_or_failed_bundle_rejected(self):
  self.check_gate([EMPTY],2);self.check_gate([STANDBY],1,72)
if __name__=='__main__':unittest.main()

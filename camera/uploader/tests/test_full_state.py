import pathlib,subprocess,tempfile,sys,unittest,os
SRC=pathlib.Path(__file__).resolve().parents[1]
NAS=SRC.parents[1]/'nas/receiver'
sys.path.insert(0,str(NAS/'tests'))
# Load shared real-camera fixtures and negative cases without unittest class import.
import importlib.util
spec=importlib.util.spec_from_file_location('nas_full_fixtures',NAS/'tests/test_full_state.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
class CameraFullStateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.d=pathlib.Path(self.tmp.name)
  self.bb=self.d/'bb';self.bb.write_text('#!/bin/sh\nexec "$@"\n');self.bb.chmod(0o700)
  self.source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0].replace('B=/bin/busybox','B='+str(self.bb)).replace('D=/setting/a7c-uploader/ram','D='+str(self.d))
 def tearDown(self):self.tmp.cleanup()
 def run_gate(self,text):
  f=self.d/'fixture';f.write_text(text);s=self.d/'test';s.write_text(self.source+'\nfull_state_idle "'+str(f)+'"\n')
  return subprocess.run(['sh',str(s)],capture_output=True,timeout=5)
 def test_camera_gate_matches_real_frames_and_rejects_mutations(self):
  for name in ['idle','standby']:
   self.assertEqual(self.run_gate((NAS/('tests/full-'+name+'.txt')).read_text()).returncode,0)
  for f in list(fixtures.invalid_frames())+[(NAS/'tests/full-running.txt').read_text()]:
   with self.subTest(tail=f[-100:]):self.assertNotEqual(self.run_gate(f).returncode,0)
 def test_report_pairs_fresh_queries_and_stops_before_directory_on_transition(self):
  for changed in [False,True]:
   d=self.d
   for name in ['calls','queried']:
    if (d/name).exists():(d/name).unlink()
   (d/'full').write_text((NAS/'tests/full-idle.txt').read_text())
   for name,body in {'full-state-probe':'cat "$TEST_DIR/full"', 'monitor':'''echo "$1" >> "$TEST_DIR/calls"
case "$1" in
 drive) printf "driveLetter = 'A'\\n";;
 recording)
  echo 'MPR Debug RecInfo'; echo '[MprMcmd][RecInfo] ====='
  if [ -f "$TEST_DIR/queried" ] && [ "$CHANGED" = 1 ]; then echo ' + line[0], contentType:Movie(XAVC), RecCnt1:1, RecCnt2:0, RecStatus:REC_STATE_RUNNING'; fi
  touch "$TEST_DIR/queried"; echo 'MON>';;
 full-info) cat "$TEST_DIR/full";;
 dir|info) echo "$1";; *) exit 99;; esac'''} .items():
    p=d/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o700)
   p=d/'test';p.write_text(self.source+'\nBOOT=test\nreport\nexit $?\n')
   r=subprocess.run(['sh',str(p)],env=dict(os.environ,TEST_DIR=str(d),CHANGED=str(int(changed))),capture_output=True,timeout=5)
   self.assertEqual(r.returncode,2 if changed else 0,r.stderr.decode())
   calls=(d/'calls').read_text().splitlines();self.assertEqual(calls,['drive','recording','full-info','recording']+([] if changed else ['dir','info']))
   if not changed:self.assertIn('A7C_FULL_STATE_BEGIN',(d/'status').read_text())
if __name__=='__main__':unittest.main()

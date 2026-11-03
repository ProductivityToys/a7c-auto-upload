"""Batch helper detection keeps executable-prefix guards and rejects no listing."""
from pathlib import Path
import os,re,shlex,subprocess,tempfile,unittest
MANAGE=Path(__file__).resolve().parents[1]/'dds_wireless_manage.sh'
class HelperScanTests(unittest.TestCase):
 def run_scan(self, targets=(), running=False, broken=False):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);proc=root/'proc';proc.mkdir();display=root/'display';display.mkdir()
   for i,target in enumerate(targets,1):
    p=proc/str(i);p.mkdir();(p/'exe').symlink_to(str(display/target) if not target.startswith('/') else target)
   # An unreadable/disappeared kernel-style entry is permitted as before.
   (proc/'90').mkdir();(proc/'90/exe').symlink_to('/missing-target')
   if running:(display/'blink-worker.running').mkdir()
   bb=root/'bb';bb.write_text('#!/bin/sh\necho "$1" >> "$TEST_CALLS"\n'+('exit 2\n' if broken else 'exec "$@"\n'));bb.chmod(0o700)
   fn=re.search(r'^inactive_helpers\(\) \{\n.*?^}\n',MANAGE.read_text(),re.M|re.S)[0].replace('/proc/',str(proc)+'/')
   script=f'''B={shlex.quote(str(bb))}
D={shlex.quote(str(display))}
cd "$D" || exit 99
mkdir -p {shlex.quote(str(proc))}/$$
ln -s /bin/sh {shlex.quote(str(proc))}/$$/exe
{fn}
inactive_helpers
'''
   p=subprocess.run(['sh'],input=script,text=True,capture_output=True,env=dict(os.environ,TEST_CALLS=str(root/'calls')),timeout=5)
   calls=(root/'calls').read_text().splitlines() if (root/'calls').exists() else []
   return p.returncode,calls,p.stderr
 def test_empty_helper_set_uses_one_listing_not_per_pid_readlink(self):
  rc,calls,err=self.run_scan(['/bin/sh','/usr/bin/python3']);self.assertEqual(rc,0,err);self.assertEqual(calls,['ls'])
 def test_each_private_helper_prefix_including_update_and_deleted_is_blocked(self):
  for target in ['capture','capture.previous','incoming','incoming.next','redraw','blink-launch','capture (deleted)']:
   with self.subTest(target=target):self.assertEqual(self.run_scan([target])[0],92)
 def test_same_basename_outside_private_display_directory_is_allowed(self):
  self.assertEqual(self.run_scan(['/usr/bin/capture','/other/incoming'])[0],0)
 def test_active_marker_blocks_without_spawning_a_listing(self):
  rc,calls,_=self.run_scan(running=True);self.assertEqual(rc,92);self.assertEqual(calls,[])
 def test_empty_or_failed_listing_cannot_authorize_management(self):
  self.assertEqual(self.run_scan(broken=True)[0],95)
if __name__=='__main__':unittest.main()

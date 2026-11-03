"""Real shell primitives: no per-message cat/wc, bounded logs, opt-in timings."""
from pathlib import Path
import os,re,subprocess,tempfile,unittest
SRC=Path(__file__).resolve().parents[1]
class LoggingTests(unittest.TestCase):
 def shell(self,body):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);(d/'uptime').write_text('100.25 200.75\n')
   (d/'bb').write_text('''#!/bin/sh
echo "$1" >> "$TEST_RAM/applets"
[ "$1" != cat ] || exit 99
exec "$@"
''');(d/'bb').chmod(0o700)
   base=(SRC.parent/'worker.sh').read_text();worker=(SRC/'worker.sh').read_text();funcs=''
   for name in ['log','uptime_seconds']:funcs+=re.search(r'^'+name+r'\(\) \{\n.*?^}\n',base,re.M|re.S)[0]
   funcs+=re.search(r'^timed\(\) \{\n.*?^}\n',worker,re.M|re.S)[0]
   funcs=funcs.replace('/proc/uptime',str(d/'uptime'))
   script=f'D={d}\nB={d}/bb\nexport TEST_RAM="$D"\n'+funcs+'\n'+body
   p=subprocess.run(['sh'],input=script,capture_output=True,text=True,timeout=5)
   self.assertEqual(p.returncode,0,p.stdout+p.stderr)
   return {f.name:f.read_text() for f in d.iterdir() if f.is_file()}
 def test_uptime_and_message_use_builtins_and_preserve_clock_format(self):
  f=self.shell('''uptime_seconds || exit 1
[ "$NOW" = 100 ] || exit 2
log 'FTP_DONE C0001.MP4'
[ ! -f "$D/applets" ] || exit 3
''');self.assertEqual(f['events.log'],'FTP_DONE C0001.MP4 100.25 200.75\n')
 def test_oversized_existing_log_is_rotated_on_first_message(self):
  f=self.shell('''while [ "$n" != 4000 ]; do printf 'abcdefghij'; n=$((${n:-0}+1)); done > "$D/events.log"
log first
[ "$(wc -c < "$D/events.previous.log" | xargs)" = 40000 ] || exit 2
''');self.assertEqual(f['events.log'],'first 100.25 200.75\n');self.assertEqual(f['applets'].splitlines(),['wc','mv'])
 def test_size_check_is_amortized_and_still_bounds_growth(self):
  f=self.shell('''log first
n=0;while [ "$n" -lt 3400 ]; do printf 'abcdefghij'; n=$((n+1)); done >> "$D/events.log"
n=2;while [ "$n" -le 16 ]; do log "message$n"; n=$((n+1)); done
[ ! -f "$D/events.previous.log" ] || exit 1
log seventeenth
[ -f "$D/events.previous.log" ] || exit 2
''');self.assertEqual(f['applets'].splitlines(),['wc','mv']);self.assertEqual(f['events.log'],'seventeenth 100.25 200.75\n')
 def test_bad_or_missing_uptime_cannot_authorize_time_checks(self):
  self.shell('''printf 'invalid\n' > "$D/uptime"
if uptime_seconds; then exit 1; fi
rm "$D/uptime"
if uptime_seconds; then exit 2; fi
''')
 def test_default_timing_preserves_status_without_log_or_applets(self):
  f=self.shell('''TIMING_ENABLED=0
fail() { return 7; }
timed receipt_read fail; rc=$?
[ "$rc" = 7 ] && [ ! -f "$D/plain-timings.log" ] && [ ! -f "$D/applets" ] || exit 1
''');self.assertNotIn('plain-timings.log',f)
 def test_explicit_timing_retains_failure_status_and_omits_arguments(self):
  f=self.shell('''TIMING_ENABLED=1
fail() { return 7; }
timed receipt_read fail secret_argument; rc=$?
[ "$rc" = 7 ] || exit 1
''');self.assertIn('op=receipt_read start=100.25 end=100.25 rc=7',f['plain-timings.log']);self.assertNotIn('secret_argument',f['plain-timings.log'])
if __name__=='__main__':unittest.main()

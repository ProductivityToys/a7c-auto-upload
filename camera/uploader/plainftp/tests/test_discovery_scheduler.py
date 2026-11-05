"""Discovery hints may change scan timing, never authorize media operations."""
from pathlib import Path
import os,re,subprocess,tempfile,unittest
SRC=Path(__file__).resolve().parents[1]
class DiscoverySchedulerTests(unittest.TestCase):
 def run_shell(self,body,code=0):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);(d/'uptime').write_text('100.0 200.0\n')
   bb=d/'bb';bb.write_text('''#!/bin/sh
case "$1:$2" in
 pidof:im.elf) echo 162;;
 sleep:*) echo "$2" >> "$TEST_RAM/sleeps";;
 *) exec "$@";;
esac
''');bb.chmod(0o700)
   (d/'return').write_text(str(code)+'\n');exe=d/'discovery';exe.write_text('''#!/bin/sh
echo "$*" >> "$TEST_RAM/calls"
cat "$TEST_RAM/return" | while read code; do exit "$code"; done
''');exe.chmod(0o700)
   exe.write_text(exe.read_text().replace('cat "$TEST_RAM/return"', '''read now rest < "$TEST_RAM/uptime"
echo "$(( ${now%.*} + $3 )).0 200.0" > "$TEST_RAM/uptime"
cat "$TEST_RAM/return"'''))
   funcs='';source=(SRC/'worker.sh').read_text()
   for name in ['cache_invalidate','discovery_wait']:
    funcs+=re.search(r'^'+name+r'\(\) \{\n.*?^}\n',source,re.M|re.S)[0]
   funcs=funcs.replace('/proc/uptime',str(d/'uptime'))
   script=f'D={d}\nB={bb}\nexport TEST_RAM="$D"\n'+funcs+'''
log() { echo "$*" >> "$D/events"; }
delay=2; QUEUE_PENDING=0; previous_card=card; stable_since=1
SNAPSHOT_AT=100; GATE_AT=100; ROOT_AT=100; ROOT_CARD=card
printf 'old verified row\n' > "$D/plain.checked"
printf 'old known row\n' > "$D/plain.known"
'''+body
   p=subprocess.run(['sh'],input=script,capture_output=True,text=True,timeout=3)
   self.assertEqual(p.returncode,0,p.stdout+p.stderr)
 def test_quiet_fallback_preserves_checked_cache(self):
  self.run_shell('''discovery_wait || exit 1
[ "$(cat "$D/calls")" = '162 wait 30 0' ] || exit 2
[ "$(cat "$D/plain.checked")" = 'old verified row' ] || exit 3
[ "$SNAPSHOT_AT" = 100 ] && [ "$previous_card" = card ] || exit 4
[ ! -f "$D/sleeps" ] || exit 5
''')
 def test_activity_and_busy_hints_rebind_snapshot_but_keep_success_facts(self):
  for code in [10,11]:
   self.run_shell('''discovery_wait || exit 1
[ "$(cat "$D/plain.checked")" = 'old verified row' ] && [ "$previous_card" = none ] && [ "$QUEUE_PENDING" = 1 ] || exit 2
[ -z "$SNAPSHOT_AT" ] && [ -z "$ROOT_AT" ] || exit 3
[ "$(cat "$D/plain.known")" = 'old known row' ] || exit 4
''',code)
 def test_failed_hint_disables_it_until_worker_restart_and_uses_original_polling(self):
  self.run_shell('''discovery_wait || exit 1
[ "$DISCOVERY_OFF" = 1 ] && [ "$(cat "$D/plain.checked")" = 'old verified row' ] || exit 2
echo again > "$D/plain.checked"
discovery_wait || exit 3
[ "$(wc -l < "$D/calls" | xargs)" = 1 ] || exit 4
[ "$(cat "$D/sleeps" | tr '\\n' ' ')" = '2 2 ' ] || exit 5
[ "$(cat "$D/plain.checked")" = again ] || exit 6
''',95)
 def test_retry_uses_bounded_hint_waits_instead_of_uninterruptible_long_sleep(self):
  self.run_shell('''for delay in 0 1 20 40 600; do discovery_wait || exit 1; done
[ "$(wc -l < "$D/calls" | xargs)" = 23 ] || exit 2
[ "$(cat "$D/sleeps")" = 1 ] || exit 3
''')
 def test_photo_layout_change_retries_hint_and_returns_to_quiet_wait(self):
  self.run_shell('''PHOTOS=1; DISCOVERY_OFF=0
discovery_wait || exit 1
[ "$DISCOVERY_OFF" = 0 ] && [ "$QUEUE_PENDING" = 1 ] || exit 2
[ "$(cat "$D/plain.checked")" = 'old verified row' ] || exit 3
echo 0 > "$D/return"
discovery_wait || exit 4
[ "$(wc -l < "$D/calls" | xargs)" = 2 ] || exit 5
[ "$(tail -1 "$D/calls")" = '162 wait 30 0' ] || exit 6
[ "$(cat "$D/sleeps")" = 2 ] || exit 7
''',95)
 def test_photo_transport_or_memory_failure_keeps_original_disable_policy(self):
  self.run_shell('''PHOTOS=1
discovery_wait || exit 1
[ "$DISCOVERY_OFF" = 1 ] || exit 2
''',72)
 def test_network_change_breaks_long_backoff_and_requests_one_health_check(self):
  self.run_shell('''delay=600; FTP_CHECK_DUE=0; FTP_CHECK_BACKOFF=600
discovery_wait || exit 1
[ "$FTP_CHECK_DUE" = 1 ] && [ "$FTP_CHECK_BACKOFF" = 10 ] || exit 2
[ "$(wc -l < "$D/calls" | xargs)" = 1 ] || exit 3
[ -z "$SNAPSHOT_AT" ] && [ "$QUEUE_PENDING" = 1 ] || exit 4
''',12)
 def test_cancel_and_missing_helper_never_authorize_or_corrupt_cache(self):
  self.run_shell('''discovery_wait || exit 1
[ "$(cat "$D/plain.checked")" = 'old verified row' ] || exit 2
rm "$D/discovery"
discovery_wait || exit 3
[ "$(cat "$D/sleeps")" = 2 ] || exit 4
''',20)
if __name__=='__main__':unittest.main()

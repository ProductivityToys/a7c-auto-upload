"""Exercise real shell cache boundaries with counted native service calls."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]


class SnapshotTests(unittest.TestCase):
    sample = '''A7C_RECORDER_SAMPLE_V1 pid=4242 ms=1234
line=0 active=1 index=0 type=256 state=1 count1=0 count2=0
line=1 active=1 index=1 type=256 state=1 count1=0 count2=0
line=2 active=0 index=0 type=0 state=0 count1=0 count2=0
line=3 active=0 index=0 type=0 state=0 count1=0 count2=0
'''

    def sample_setup(self, sample=None, rc=0):
        sample = self.sample if sample is None else sample
        return '''
discovery_pid=4242
cat > "$D/discovery" <<'PROBE'
#!/bin/sh
echo sample >> "$TEST_RAM/native-calls"
cat "$TEST_RAM/sample"
exit ''' + str(rc) + '''
PROBE
chmod 700 "$D/discovery"
printf '%s' ''' + shlex.quote(sample) + ''' > "$D/sample"
'''

    def run_shell(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'card').write_text('cardA\n')
            (d / 'uptime').write_text('100.0 200.0\n')
            (d / 'usb-state').write_text('UNKNOWN\n')
            (d / 'rows').write_text('C0001.MP4 24 C0001M01.XML 2176 date date\n')
            scripts = {
                'bb': '#!/bin/sh\nexec "$@"\n',
                'local-media': '''#!/bin/sh
case "$1" in
 info) if grep -q '^CARD=' "$3"; then sed -n 's/^CARD=//p' "$3"; else sed -n '1p' "$3"; fi;;
 newest) sed -n '/^C[0-9]/p' "$3";;
 *) exit 90;;
esac
''',
                'monitor': '''#!/bin/sh
echo "$1" >> "$TEST_RAM/native-calls"
case "$1" in
 filesystem) [ ! -f "$TEST_RAM/clip-writer" ] || exit 90
       printf "driveLetter = 'A'\\n"
       printf 'CARD='; cat "$TEST_RAM/card"
       cat "$TEST_RAM/rows"
       [ ! -f "$TEST_RAM/open-clip" ] || cat "$TEST_RAM/open-clip";;
 drive) printf "driveLetter = 'A'\\n";;
 info) [ ! -f "$TEST_RAM/clip-writer" ] || exit 90
       cat "$TEST_RAM/card"
       [ ! -f "$TEST_RAM/open-clip" ] || cat "$TEST_RAM/open-clip";;
 dir) cat "$TEST_RAM/rows";;
 *) exit 90;;
esac
''',
                'sd-monitor': '''#!/bin/sh
echo "$1" >> "$TEST_RAM/sd-calls"
[ ! -f "$TEST_RAM/root-failure" ] || exit 90
case "$1" in
 root) echo root-list;;
 context) [ ! -f "$TEST_RAM/clip-writer" ] || exit 90
          cat "$TEST_RAM/card"
          [ ! -f "$TEST_RAM/open-clip" ] || cat "$TEST_RAM/open-clip";;
 *) exit 90;;
esac
''',
            }
            for name, text in scripts.items():
                (d / name).write_text(text)
                (d / name).chmod(0o700)
            source = (SRC / 'worker.sh').read_text()
            functions = source[source.index('timed() {'):source.index('receipt_load() {')]
            runtime = (SRC.parent / 'worker.sh').read_text()
            functions = runtime[runtime.index('wait_child() {'):runtime.index('scan_hold_stop() {')] + functions
            functions = functions.replace('/proc/uptime', str(d / 'uptime'))
            functions = functions.replace('/sys/class/udc/dwc3.0/current_speed', str(d / 'usb-state'))
            script = f'''D={shlex.quote(str(d))}
B="$D/bb"
export TEST_RAM="$D"
TEST_NOW=100; REC_OK=1
{functions}
uptime_seconds() {{ NOW=$TEST_NOW; }}
recording_idle() {{ echo recording >> "$D/native-calls"; [ "$REC_OK" = 1 ]; }}
report() {{
 echo report >> "$D/native-calls"
 [ "$REC_OK" = 1 ] || return 1
 LETTER=A
 cp "$D/card" "$D/info"
 cp "$D/rows" "$D/dir"
}}
{body}
'''
            p = subprocess.run(['sh', '-e'], input=script, text=True,
                               capture_output=True, timeout=5, env=os.environ.copy())
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            return {f.name: f.read_text() for f in d.iterdir() if f.is_file()}

    def test_backlog_reuses_whole_snapshot_without_per_clip_info(self):
        files = self.run_shell('''
media_gate
TEST_NOW=105; media_poll
[ "$SNAPSHOT_AT" = 100 ] && [ "$GATE_AT" = 100 ]
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem'])

    def test_connected_usb_does_not_read_card_and_unplug_resumes(self):
        files = self.run_shell('''
media_poll
ROOT_AT=100; ROOT_CARD=cardA
echo high-speed > "$D/usb-state"
if media_poll; then exit 99; fi
[ -z "$SNAPSHOT_AT" ] && [ -z "$ROOT_AT" ]
echo UNKNOWN > "$D/usb-state"
media_poll
''')
        self.assertEqual(files['native-calls'].splitlines(), ['filesystem', 'filesystem'])

    def test_usb_blocks_transfer_and_receipt_write_even_with_cached_directory(self):
        files = self.run_shell('''
media_gate
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
echo super-speed > "$D/usb-state"
if source_same; then exit 99; fi
if receipt_card_ready; then exit 99; fi
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem'])
        self.assertNotIn('sd-calls', files)

    def test_unknown_usb_state_waits_without_card_access(self):
        files = self.run_shell('''
echo invalid > "$D/usb-state"
if media_poll; then exit 99; fi
rm "$D/usb-state"
if media_poll; then exit 99; fi
''')
        self.assertNotIn('native-calls', files)

    def test_backlog_window_expiry_refreshes_directory_without_slow_recorder_query(self):
        files = self.run_shell('''
media_gate
recording_idle() { echo slow-recording >> "$D/native-calls"; return 99; }
TEST_NOW=125; media_poll
[ "$SNAPSHOT_AT" = 125 ] && [ "$GATE_AT" = 125 ]
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
TEST_NOW=126; source_checked
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem', 'filesystem'])

    def test_read_only_selection_reuses_fresh_gate_but_transfer_rechecks(self):
        files = self.run_shell('''
media_gate
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
TEST_NOW=101; source_checked
source_same
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem', 'recording', 'info'])

    def test_expired_snapshot_and_clock_rollback_rebind_read_only_filesystem(self):
        files = self.run_shell('''
media_gate
TEST_NOW=131; media_poll
TEST_NOW=130; media_poll
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem'] + ['filesystem'] * 2)

    def test_initial_read_only_bind_does_not_authorize_transfer_when_recording_unknown(self):
        files = self.run_shell('''
REC_OK=0
media_poll
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
source_checked
if source_same; then exit 99; fi
[ -z "$SNAPSHOT_AT" ]
''')
        # Recorder and card info run concurrently; a failed recorder check still
        # denies the transfer even though the info query also ran.
        calls = files['native-calls'].splitlines()
        self.assertEqual(calls[0], 'filesystem')
        self.assertEqual(sorted(calls[1:]), ['info', 'recording'])

    def test_pre_copy_recorder_and_info_checks_run_concurrently(self):
        files = self.run_shell('''
media_poll
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
recording_idle() { echo recording-start >> "$D/native-calls"; sleep 1; echo recording-end >> "$D/native-calls"; }
cp "$D/monitor" "$D/monitor.real"
printf '#!/bin/sh\n[ "$1" != info ] || { echo info-start >> "$TEST_RAM/native-calls"; sleep 1; echo info-end >> "$TEST_RAM/native-calls"; }\nexec "$TEST_RAM/monitor.real" "$@"\n' > "$D/monitor"
source_same
''')
        calls = files['native-calls'].splitlines()
        # Both started before either finished.
        self.assertLess(max(calls.index('recording-start'), calls.index('info-start')),
                        min(calls.index('recording-end'), calls.index('info-end')))

    def test_initial_bind_rejects_open_clip_before_directory_read(self):
        files = self.run_shell(r'''
printf '%s\n' 'file = "D:\PRIVATE\M4ROOT\CLIP\C0001.MP4"' > "$D/open-clip"
if media_poll; then exit 99; fi
[ -z "$SNAPSHOT_AT" ]
''')
        self.assertEqual(files['native-calls'].splitlines(), ['filesystem'])

    def test_aged_read_only_selection_refreshes_whole_filesystem_snapshot(self):
        files = self.run_shell('''
media_gate
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
TEST_NOW=109; source_checked
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem', 'filesystem'])

    def test_refresh_rejects_writer_and_binds_changed_card_with_fresh_directory(self):
        self.run_shell("""
media_gate
ROOT_AT=100; ROOT_CARD=cardA
touch "$D/clip-writer"
TEST_NOW=109
if media_poll; then exit 99; fi
[ -z "$SNAPSHOT_AT" ] && [ -z "$GATE_AT" ] && [ -z "$ROOT_AT" ]
""")
        self.run_shell("""
media_gate
ROOT_AT=100; ROOT_CARD=cardA
echo cardB > "$D/card"
TEST_NOW=109; media_poll
[ "$CARD" = cardB ] && [ "$SNAPSHOT_CARD" = cardB ] && [ "$SNAPSHOT_AT" = 109 ] && [ -z "$ROOT_AT" ]
""")

    def test_even_read_only_open_clip_handle_rejects_fast_path(self):
        self.run_shell(r'''
media_gate
ROOT_AT=100
printf '%s\n' '  status = open, read' '  file & ext name = "D:\PRIVATE\M4ROOT\CLIP\C0001.MP4"' > "$D/open-clip"
TEST_NOW=109
if media_poll; then exit 99; fi
[ -z "$SNAPSHOT_AT" ] && [ -z "$ROOT_AT" ]
''')

    def test_read_only_backlog_does_not_force_a_second_stability_snapshot(self):
        files=self.run_shell("""
media_poll
QUEUE_PENDING=1
TEST_NOW=101; media_poll
[ "$SNAPSHOT_AT" = 100 ]
TEST_NOW=102; media_poll
[ "$SNAPSHOT_AT" = 100 ]
""")
        self.assertEqual(files['native-calls'].splitlines(),['filesystem'])

    def test_idle_poll_refreshes_directory_to_discover_short_new_clip(self):
        files = self.run_shell('''
media_gate
stable_since=90; QUEUE_PENDING=0
TEST_NOW=101; media_poll
[ "$SNAPSHOT_AT" = 101 ]
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem', 'filesystem'])

    def test_directory_change_invalidates_root_listing(self):
        self.run_shell('''
media_gate
ROOT_AT=100; ROOT_CARD=cardA
echo 'C0002.MP4 25 C0002M01.XML 2176 date date' >> "$D/rows"
TEST_NOW=131; media_poll
[ -z "$ROOT_AT" ]
''')

    def test_backlog_window_is_bounded_and_new_directory_is_not_hidden(self):
        files = self.run_shell("""
media_gate
TEST_NOW=108; media_poll
[ "$SNAPSHOT_AT" = 100 ]
echo 'C0002.MP4 25 C0002M01.XML 2176 date date' >> "$D/rows"
TEST_NOW=109; media_poll
[ "$SNAPSHOT_AT" = 109 ] && grep -q C0002.MP4 "$D/plain.entries"
""")
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem', 'filesystem'])

    def test_read_only_cache_never_authorizes_transfer_after_card_change(self):
        files = self.run_shell("""
media_gate
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
echo cardB > "$D/card"
TEST_NOW=101; source_checked
if source_same; then exit 99; fi
""")
        self.assertEqual(files['native-calls'].splitlines(), ['recording', 'filesystem', 'recording', 'info'])

    def test_root_reuse_ttl_card_and_force_refresh(self):
        files = self.run_shell('''
CARD=cardA; DRIVE=A
receipt_root cached
TEST_NOW=110; receipt_root cached
receipt_root fresh
TEST_NOW=141; receipt_root cached
CARD=cardB; receipt_root cached
TEST_NOW=140; receipt_root cached
''')
        self.assertEqual(files['sd-calls'].splitlines(), ['root'] * 5)

    def test_failed_root_refresh_never_leaves_valid_cache(self):
        self.run_shell('''
CARD=cardA; DRIVE=A
receipt_root cached
touch "$D/root-failure"
if receipt_root fresh; then exit 99; fi
[ -z "$ROOT_AT" ]
''')

    def test_receipt_write_rechecks_recorder_card_and_handles_without_listing_videos(self):
        files=self.run_shell("""
media_gate
SOURCE_CARD=$CARD; DRIVE=$LETTER
: > "$D/rows"
receipt_card_ready
""")
        self.assertEqual(files['native-calls'].splitlines(), ['recording','filesystem','recording'])
        self.assertEqual(files['sd-calls'].splitlines(), ['context'])
        self.assertEqual(files['receipt.root'], files['receipt.context'])

    def test_receipt_write_rejects_recording_card_change_or_open_clip(self):
        for change in ('REC_OK=0','echo cardB > "$D/card"','touch "$D/clip-writer"',
                       r'''printf '%s\n' 'file = "D:\PRIVATE\M4ROOT\CLIP\C0001.MP4"' > "$D/open-clip"'''):
            with self.subTest(change=change):
                self.run_shell("""
media_gate
SOURCE_CARD=$CARD; DRIVE=$LETTER
"""+change+"""
if receipt_card_ready; then exit 99; fi
[ -z "$SNAPSHOT_AT" ]
""")

    def test_receipt_finish_reuses_root_without_extending_its_ttl(self):
        files = self.run_shell('''
media_gate
SOURCE_CARD=$CARD; DRIVE=$LETTER
receipt_root cached
TEST_NOW=109
receipt_card_ready
[ "$ROOT_AT" = 100 ]
receipt_root cached
TEST_NOW=131
receipt_card_ready
[ "$ROOT_AT" = 131 ]
''')
        self.assertEqual(files['native-calls'].splitlines(),
                         ['recording', 'filesystem', 'recording', 'info', 'recording'])
        self.assertEqual(files['sd-calls'].splitlines(), ['root', 'context'])

    def test_cached_root_never_bypasses_current_card_or_open_handle_check(self):
        for change in ('echo cardB > "$D/card"', 'touch "$D/clip-writer"',
                       r'''printf '%s\n' 'file = "D:\PRIVATE\M4ROOT\CLIP\C0001.MP4"' > "$D/open-clip"'''):
            with self.subTest(change=change):
                self.run_shell('''
media_gate
SOURCE_CARD=$CARD; DRIVE=$LETTER
receipt_root cached
TEST_NOW=109
''' + change + '''
if receipt_card_ready; then exit 99; fi
[ -z "$ROOT_AT" ]
''')

    def test_receipt_uses_current_sample_but_video_still_uses_complete_query(self):
        files = self.run_shell(self.sample_setup() + '''
media_gate
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
source_same
receipt_card_ready
''')
        self.assertEqual(files['native-calls'].splitlines(),
                         ['recording', 'filesystem', 'recording', 'info', 'sample'])
        self.assertEqual(files['sd-calls'].splitlines(), ['context'])

    def test_transfer_refreshes_info_but_does_not_extend_directory_ttl(self):
        files=self.run_shell('''
media_poll
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
TEST_NOW=107; source_same
[ "$SNAPSHOT_AT" = 100 ]
TEST_NOW=109; source_same
[ "$SNAPSHOT_AT" = 109 ]
''')
        self.assertEqual(files['native-calls'].splitlines(),
                         ['filesystem','recording','info','recording','filesystem'])

    def test_reused_directory_never_bypasses_fresh_writer_or_card_check(self):
        for change in ('touch "$D/clip-writer"','echo cardB > "$D/card"',
                       r'''printf '%s\n' 'file = "D:\PRIVATE\M4ROOT\CLIP\C0001.MP4"' > "$D/open-clip"'''):
            with self.subTest(change=change):
                self.run_shell('''
media_poll
SOURCE_ROW=$(cat "$D/plain.entries"); SOURCE_CARD=$CARD; DRIVE=$LETTER
TEST_NOW=101
'''+change+'''
if source_same; then exit 99; fi
[ -z "$SNAPSHOT_AT" ]
''')

    def test_unknown_incomplete_or_busy_sample_falls_back_to_complete_query(self):
        samples = [self.sample.replace('state=1', 'state=3', 1),
                   self.sample.replace('count1=0', 'count1=1', 1),
                   self.sample.replace('type=256', 'type=7', 1),
                   self.sample.replace('active=0', 'active=1', 1),
                   self.sample.replace('pid=4242', 'pid=999'),
                   self.sample.replace('ms=1234', 'ms=wrong ms=1234'),
                   self.sample.rsplit('line=3', 1)[0],
                   self.sample + 'unexpected\n', self.sample + 'unterminated']
        for sample in samples:
            with self.subTest(sample=sample):
                files = self.run_shell(self.sample_setup(sample) + 'receipt_recording_idle\n')
                self.assertEqual(files['native-calls'].splitlines(), ['sample', 'recording'])

    still = """A7C_RECORDER_SAMPLE_V1 pid=4242 ms=1234
line=0 active=1 index=0 type=1 state=1 count1=0 count2=0
line=1 active=0 index=0 type=0 state=0 count1=0 count2=0
line=2 active=0 index=0 type=0 state=0 count1=0 count2=0
line=3 active=0 index=0 type=0 state=0 count1=0 count2=0
"""

    def test_photo_standby_sample_authorizes_receipt_fast_path(self):
        files = self.run_shell(self.sample_setup(self.still) + 'receipt_recording_idle\n')
        self.assertEqual(files['native-calls'].splitlines(), ['sample'])

    def test_busy_or_mixed_photo_sample_falls_back_to_complete_query(self):
        samples = [self.still.replace('state=1', 'state=3', 1),
                   self.still.replace('count1=0', 'count1=1', 1),
                   self.still.replace('count2=0', 'count2=2', 1),
                   self.still.replace('line=1 active=0 index=0 type=0', 'line=1 active=1 index=1 type=256', 1),
                   self.still.replace('type=1 ', 'type=2 ', 1)]
        for sample in samples:
            with self.subTest(sample=sample):
                files = self.run_shell(self.sample_setup(sample) + 'receipt_recording_idle\n')
                self.assertEqual(files['native-calls'].splitlines(), ['sample', 'recording'])

    def test_probe_failure_does_not_trust_even_valid_old_stdout(self):
        files = self.run_shell(self.sample_setup(rc=95) + 'receipt_recording_idle\n')
        self.assertEqual(files['native-calls'].splitlines(), ['sample', 'recording'])

    def test_disabled_probe_and_failed_full_query_cannot_authorize_receipt(self):
        files = self.run_shell(self.sample_setup() + '''
DISCOVERY_OFF=1; REC_OK=0
if receipt_recording_idle; then exit 99; fi
''')
        self.assertEqual(files['native-calls'].splitlines(), ['recording'])
        self.run_shell(self.sample_setup(self.sample.replace('state=1', 'state=5')) + '''
REC_OK=0
if receipt_recording_idle; then exit 99; fi
''')

    def test_exact_idle_sample_never_bypasses_current_card_or_handles(self):
        for change in ('echo cardB > "$D/card"', 'touch "$D/clip-writer"',
                       r'''printf '%s\n' 'file = "D:\PRIVATE\M4ROOT\CLIP\C0001.MP4"' > "$D/open-clip"'''):
            with self.subTest(change=change):
                self.run_shell(self.sample_setup() + '''
media_gate
SOURCE_CARD=$CARD; DRIVE=$LETTER
receipt_root cached
''' + change + '''
if receipt_card_ready; then exit 99; fi
[ -z "$ROOT_AT" ]
''')


if __name__ == '__main__':
    unittest.main()

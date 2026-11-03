"""Exercise the real worker loop: idle networking stops, discovery/retry remain live."""
import os,pathlib,subprocess,tempfile,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]

class QuietTests(unittest.TestCase):
 def test_native_echo_variation_is_quiet_but_entries_errors_and_drive_are_not(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   bb=d/'bb';bb.write_text('#!/bin/sh\ncase "$1:$2" in cat:/proc/uptime) echo "100.00 0.00";; *) exec "$@";; esac\n');bb.chmod(0o700)
   cmd='IFSYS dir A:/PRIVATE/M4ROOT/CLIP'
   row='[IFSYS]a-----     46148105 2026-10-15 00:31:22 C0196.MP4'
   original=cmd+'\n'+cmd+'\n'+cmd+'\r\n'+row+'\r\nMWF>\n'
   varied=cmd+'\n'+cmd+'\n\r\nMWF>'+cmd+'\r\n'+row+'\r\nMWF>\n'
   (d/'initial').write_text(original)
   (d/'clock').write_text('100.00 0.00\n')
   source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
   source=source.replace('B=/bin/busybox',f'B={bb}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
   source=source.replace('/proc/uptime',str(d/'clock'))
   source+='''
LETTER=A; QUIET_ARMED=0; QUIET_LAST=0; QUIET_SIGNATURE=none
$B cp "$D/initial" "$D/dir"
quiet_unchanged
QUIET_SIGNATURE=$SCAN_SIGNATURE; QUIET_ARMED=1; QUIET_LAST=100
$B cp "$D/next" "$D/dir"
LETTER=$1
quiet_unchanged
exit $?
'''
   script=d/'test.sh';script.write_text(source)
   cases=[(varied,'A',0),(varied.replace('46148105','46148106'),'A',1),
          (varied.replace('00:31:22','00:31:23'),'A',1),
          (varied.replace(row,''),'A',1),(varied+'[ERR] failed\n','A',1),
          (varied,'B',1)]
   for data,drive,expected in cases:
    (d/'next').write_text(data)
    r=subprocess.run(['sh',str(script),drive],capture_output=True,timeout=3)
    self.assertEqual(r.returncode,expected,(data,drive,r.stderr.decode()))

 def test_malformed_idle_plan_cannot_arm_quiet(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
   source=source.replace('D=/setting/a7c-uploader/ram',f'D={d}')
   source=source.replace('/proc/uptime',str(d/'clock'))
   source+='\nCLOCK_OK=1; NOW=10; SCAN_SIGNATURE=test; QUIET_ARMED=0\narm_quiet\nrc=$?\n[ "$rc" = 1 ] && [ "$QUIET_ARMED" = 0 ]\n'
   script=d/'invalid.sh';script.write_text(source)
   for value in ['IDLE 0','IDLE -1','IDLE 241','IDLE 9999999999','IDLE 08','IDLE x','IDLE 10 extra','IDLE','WAIT 10']:
    (d/'plan').write_text(value+'\n')
    r=subprocess.run(['sh',str(script)],capture_output=True,timeout=3)
    self.assertEqual(r.returncode,0,(value,r.stderr.decode()))
 def test_idle_changes_recording_clock_gap_and_network_retry(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);p=d/'persistent';p.mkdir()
   (p/'enabled').touch();(p/'token').write_text('a'*64)
   def exe(name,body):
    f=d/name;f.write_text('#!/bin/sh\n'+body);f.chmod(0o700);return f
   bb=exe('bb','''case "$1:$2" in
cat:/proc/uptime) cat "$TEST_DIR/clock";;
cat:/proc/sys/kernel/random/boot_id) echo 11111111-1111-1111-1111-111111111111;;
sleep:*) echo "$2" >> "$TEST_DIR/sleeps";;
*) exec "$@";; esac
''')
   exe('net','''n=$(cat "$TEST_DIR/scan")
case "$1:$2" in
put:status.txt) echo "$n" >> "$TEST_DIR/puts"; [ "$n" != 9 ];;
get:plan.txt)
 echo "$n" >> "$TEST_DIR/gets"
 if [ "$n" = 1 ]; then echo WAIT > "$3"; else echo 'IDLE 120' > "$3"; fi;;
*) exit 97;; esac
''')
   source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
   source=source.replace('B=/bin/busybox',f'B={bb}').replace('P=/setting/a7c-uploader',f'P={p}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
   source=source.replace('/proc/uptime',str(d/'clock'))
   source+='''
# Startup lease lifecycle is exercised separately in test_scan_hold.py.
scan_hold_start() { SCAN_HOLD=; }
n=0
report() {
 n=$((n+1)); echo "$n" > "$D/scan"; LETTER=B
 case "$n" in
  1) stamp=100;; 2) stamp=120;; 3) stamp=140;; 4) stamp=160;;
  5) stamp=180;; 6) stamp=200;; 7) stamp=20;; 8) stamp=140;;
  9) stamp=160;; 10) stamp=180;; 11) stamp=200; : > "$D/stop";;
  *) exit 96;;
 esac
 echo "$stamp.00 0.00" > "$D/clock"
 if [ "$n" -lt 4 ]; then echo original > "$D/dir"
 elif [ "$n" -lt 9 ]; then echo new_video > "$D/dir"
 else echo another_video > "$D/dir"; fi
 [ "$n" != 5 ] || return 2
 echo status > "$D/status"
}
run
exit $?
'''
   script=d/'test.sh';script.write_text(source)
   r=subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_DIR=str(d)),capture_output=True,timeout=8)
   self.assertEqual(r.returncode,42,r.stderr.decode())
   self.assertEqual((d/'puts').read_text().splitlines(),['1','2','4','6','7','8','9','10'])
   self.assertEqual((d/'gets').read_text().splitlines(),['1','2','4','6','7','8','10'])
   self.assertIn('20',(d/'sleeps').read_text().splitlines())
   self.assertFalse((d/'lease.ready').exists())
   self.assertEqual(sorted(x.name for x in p.iterdir()),['enabled','token'])

class LongQuietTests(unittest.TestCase):
 def test_continuous_unchanged_idle_outlives_old_deadline_but_gap_or_change_ends_it(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp)
   bb=d/'bb';bb.write_text('#!/bin/sh\ncase "$1:$2" in cat:/proc/uptime) cat "'+str(d/'clock')+'";; *) exec "$@";; esac\n');bb.chmod(0o700)
   source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0].replace('B=/bin/busybox','B='+str(bb)).replace('D=/setting/a7c-uploader/ram','D='+str(d))
   source=source.replace('/proc/uptime',str(d/'clock'))
   source+='''
LETTER=B; QUIET_ARMED=0; QUIET_LAST=0; QUIET_SIGNATURE=none
echo original > "$D/dir"
echo "100.00 0.00" > "$D/clock"
quiet_unchanged
echo "IDLE 120" > "$D/plan"
arm_quiet || exit 10
n=110
while [ "$n" -le 3700 ]; do echo "$n.00 0.00" > "$D/clock"; quiet_unchanged || exit 11; n=$((n+10)); done
echo "3800.00 0.00" > "$D/clock"
quiet_unchanged && exit 12
echo "3690.00 0.00" > "$D/clock"
quiet_unchanged && exit 13
echo "3710.00 0.00" > "$D/clock"
echo new_video > "$D/dir"
quiet_unchanged && exit 14
exit 0
'''
   script=d/'test.sh';script.write_text(source)
   result=subprocess.run(['sh',str(script)],capture_output=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr.decode())

if __name__=='__main__':unittest.main()

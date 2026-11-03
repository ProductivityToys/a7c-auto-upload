"""First scan has one bounded lease; all exit paths release before uploading."""
import os, pathlib, subprocess, tempfile, unittest
SRC=pathlib.Path(__file__).resolve().parents[1]/'worker.sh'

class ScanHoldTests(unittest.TestCase):
 def test_first_scan_release_and_no_reacquisition(self):
  for mode in ('meta','idle','network','busy','wait','release_error'):
   with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
    d=pathlib.Path(tmp);p=d/'persistent';p.mkdir()
    (p/'enabled').touch();(p/'token').write_text('a'*64)
    def exe(name,body):
     f=d/name;f.write_text('#!/bin/sh\n'+body);f.chmod(0o700);return f
    bb=exe('bb','''case "$1:$2" in
cat:/proc/uptime) echo '100.0 0.0';;
cat:/proc/sys/kernel/random/boot_id) echo 11111111-1111-1111-1111-111111111111;;
sleep:*) sleep .02;;
*) exec "$@";; esac
''')
    exe('lease','''[ "$1:$2" = --upload-lease:90 ] || exit 98
echo start >> "$TEST_DIR/lease-starts"
touch "$TEST_DIR/active" "$TEST_DIR/lease.ready"
n=0
while [ ! -f "$TEST_DIR/lease.done" ] && [ "$n" -lt 12 ]; do sleep .01; n=$((n+1)); done
rm "$TEST_DIR/active"
[ "$TEST_MODE" != release_error ] || exit 1
echo 'PROBE_DONE set=0 clear=0 guardian_status=0'
''')
    source=SRC.read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
    source=source.replace('B=/bin/busybox','B='+str(bb)).replace('P=/setting/a7c-uploader','P='+str(p)).replace('D=/setting/a7c-uploader/ram','D='+str(d))
    source+='''
nscan=0
report() {
 nscan=$((nscan+1)); LETTER=A; echo original > "$D/dir"
 if [ "$nscan" = 1 ]; then [ -f "$D/active" ] || exit 95; fi
 if [ "$nscan" = 14 ]; then [ ! -e "$D/active" ] || exit 96; : > "$D/stop"; fi
 [ "$TEST_MODE" != busy ]
}
put() { [ "$TEST_MODE" != network ]; }
plan() {
 case "$TEST_MODE" in
  meta) echo 'META A C0001.MP4 100 C0001M01.XML 3 aaaaaaaaaaaaaaaaaaaaaaaa';;
  wait) echo WAIT;;
  *) echo 'IDLE 120';;
 esac > "$D/plan"
}
scan_diagnostic() { :; }
attempt() { [ ! -e "$D/active" ] || exit 97; : > "$D/stop"; return 2; }
run
exit $?
'''
    script=d/'test.sh';script.write_text(source)
    result=subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_DIR=str(d),TEST_MODE=mode),capture_output=True,timeout=5)
    self.assertEqual(result.returncode,90 if mode=='release_error' else 42,result.stderr.decode())
    self.assertFalse((d/'active').exists())
    if mode!='release_error':
     self.assertFalse((d/'lease.ready').exists());self.assertFalse((d/'lease.done').exists())
    self.assertEqual((d/'lease-starts').read_text(),'start\n')
    self.assertEqual(sorted(x.name for x in p.iterdir()),['enabled','token'])

if __name__=='__main__': unittest.main()

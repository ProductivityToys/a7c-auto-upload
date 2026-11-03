"""Normal worker retries metadata network failure; diagnostic mode pauses safely."""
import os,pathlib,subprocess,tempfile,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class RetryTests(unittest.TestCase):
 def test_normal_retry_and_diagnostic_pause(self):
  for diagnostic in (False,True):
   with self.subTest(diagnostic=diagnostic),tempfile.TemporaryDirectory() as tmp:
    d=pathlib.Path(tmp);p=d/'persistent';p.mkdir()
    (p/'enabled').touch();(p/'token').write_text('a'*64)
    if diagnostic:(p/'pause-after-failure').touch()
    def exe(name,body):
     f=d/name;f.write_text('#!/bin/sh\n'+body);f.chmod(0o700);return f
    bb=exe('bb','''case "$1:$2" in
wc:-c) wc -c | xargs;;
cat:/proc/uptime) echo TEST_PROC;;
cat:/proc/sys/kernel/random/boot_id) echo 11111111-1111-1111-1111-111111111111;;
sleep:*) echo "$2" >> "$TEST_DIR/sleeps"; sleep .05;;
*) exec "$@";; esac
''')
    exe('lease','''touch "$TEST_DIR/lease.ready"
n=0
while [ ! -f "$TEST_DIR/lease.done" ]; do sleep .01; n=$((n+1)); [ "$n" -lt 500 ] || exit 99; done
echo RELEASE_CONFIRMED
echo "PROBE_DONE set=0 clear=0 guardian_status=0"
''')
    exe('monitor','[ -f "$TEST_DIR/lease.ready" ] || exit 98\nprintf xml > "$TEST_DIR/metadata.xml"\n')
    exe('net','''case "$1:$2" in
put:status.txt) rm -f "$TEST_DIR/metadata-sent";;
get:plan.txt)
 if [ -f "$TEST_DIR/metadata-sent" ]; then echo 'SKIP aaaaaaaaaaaaaaaaaaaaaaaa' > "$3"
 else echo 'META B C0001.MP4 100 C0001M01.XML 3 aaaaaaaaaaaaaaaaaaaaaaaa' > "$3"; fi;;
put:metadata-*)
 if [ ! -f "$TEST_DIR/failed-once" ]; then touch "$TEST_DIR/failed-once"; exit 1; fi
 touch "$TEST_DIR/metadata-sent";;
put:result.txt)
 if [ ! -f "$TEST_DIR/result-1" ]; then cp "$3" "$TEST_DIR/result-1"
 else cp "$3" "$TEST_DIR/result-2"; touch "$TEST_DIR/stop"; fi;;
*) exit 97;; esac
''')
    source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
    source=source.replace('B=/bin/busybox',f'B={bb}').replace('P=/setting/a7c-uploader',f'P={p}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
    source+='\nreport() { LETTER=B; echo mock_status > "$D/status"; }\nrun\nexit $?\n'
    script=d/'test.sh';script.write_text(source)
    r=subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_DIR=str(d)),capture_output=True,timeout=12)
    self.assertEqual(r.returncode,42,r.stderr.decode())
    first=(d/'result-1').read_text();self.assertIn('attempt_rc=1',first);self.assertIn('lease_rc=0',first);self.assertIn('RELEASE_CONFIRMED',first)
    self.assertFalse((d/'source.fifo').exists())
    if diagnostic:
     self.assertFalse((d/'result-2').exists());self.assertTrue((p/'last-diagnostic.txt').exists())
    else:
     second=(d/'result-2').read_text();self.assertIn('attempt_rc=2',second);self.assertIn('lease_rc=0',second)
     self.assertIn('20',(d/'sleeps').read_text().splitlines())
     self.assertFalse((p/'last-diagnostic.txt').exists());self.assertFalse((p/'last-start.txt').exists())
if __name__=='__main__':unittest.main()

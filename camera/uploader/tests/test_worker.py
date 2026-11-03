"""Exercise metadata failure/skip paths with a real child lease and shell worker."""
import os,pathlib,subprocess,tempfile,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class WorkerTests(unittest.TestCase):
 def test_metadata_paths_release_lease_and_report(self):
  for mode,expected in [('open_error',1),('empty',1),('send_error',1),('skip',2)]:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
    d=pathlib.Path(tmp);p=d/'persistent';p.mkdir();(p/'pause-after-failure').touch()
    def exe(name,body):
     f=d/name;f.write_text('#!/bin/sh\n'+body);f.chmod(0o700);return f
    bb=exe('bb','case "$1:$2" in wc:-c) wc -c | xargs;; cat:/proc/uptime) echo TEST_PROC;; *) exec "$@";; esac\n')
    exe('lease','touch "$TEST_DIR/lease.ready"\nn=0\nwhile [ ! -f "$TEST_DIR/lease.done" ]; do sleep .05; n=$((n+1)); [ "$n" -lt 100 ] || exit 99; done\necho RELEASE_CONFIRMED\n')
    exe('monitor','[ -f "$TEST_DIR/lease.ready" ] || exit 98\ncase "$TEST_MODE" in open_error) echo "Cannot open file"; exit 73;; empty) : > "$TEST_DIR/metadata.xml";; *) printf xml > "$TEST_DIR/metadata.xml";; esac\n')
    exe('net','case "$1:$2" in put:metadata-*) [ "$TEST_MODE" != send_error ];; get:plan.txt) echo "SKIP aaaaaaaaaaaaaaaaaaaaaaaa" > "$3";; put:result.txt) cp "$3" "$TEST_DIR/received-result";; *) exit 97;; esac\n')
    source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
    source=source.replace('B=/bin/busybox',f'B={bb}').replace('P=/setting/a7c-uploader',f'P={p}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
    source+='\nBOOT=test; DRIVE=B; LETTER=B; VIDEO=C0001.MP4; XML=C0001M01.XML; SIZE=100; XSIZE=3; ATTEMPT=aaaaaaaaaaaaaaaaaaaaaaaa\nattempt\nexit $?\n'
    script=d/'test.sh';script.write_text(source)
    r=subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_DIR=str(d),TEST_MODE=mode),capture_output=True,timeout=12)
    self.assertEqual(r.returncode,expected,r.stderr.decode())
    result=(d/'received-result').read_text();self.assertIn('lease_rc=0',result);self.assertIn('RELEASE_CONFIRMED',result)
    self.assertEqual(result,(p/'last-diagnostic.txt').read_text())
    self.assertFalse((d/'source.fifo').exists())
if __name__=='__main__':unittest.main()

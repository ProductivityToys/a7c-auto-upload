"""Closed recording gates remain safe and observable without NAND/network writes."""
import os
import pathlib
import subprocess
import tempfile
import unittest

SRC = pathlib.Path(__file__).resolve().parents[1]


class GateTests(unittest.TestCase):
 def test_unknown_busy_and_partial_states_do_not_read_media(self):
  standby = 'contentType:Movie(XAVC), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY'
  for rec in ['[MprMcmd][RecInfo] =====\nMON>\n', standby+'\n',
              standby+'\n'+standby.replace('STANDBY', 'RUNNING')+'\n']:
   with self.subTest(rec=rec), tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp); p = d/'persistent'; p.mkdir()
    (d/'rec-fixture').write_text(rec)
    def exe(name, body):
     f=d/name; f.write_text('#!/bin/sh\n'+body); f.chmod(0o700); return f
    bb=exe('bb', 'case "$1:$2" in cat:/proc/uptime) echo "100.00 200.00";; *) exec "$@";; esac\n')
    exe('monitor', '''echo "$1" >> "$TEST_DIR/calls"
case "$1" in
 drive) printf "driveLetter = 'A'\\n";;
 recording) cat "$TEST_DIR/rec-fixture";;
 *) exit 97;; esac
''')
    exe('net', 'echo NETWORK > "$TEST_DIR/unexpected-network"; exit 98\n')
    source=(SRC/'worker.sh').read_text().split("\n$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs '")[0]
    source=source.replace('B=/bin/busybox',f'B={bb}').replace('P=/setting/a7c-uploader',f'P={p}').replace('D=/setting/a7c-uploader/ram',f'D={d}')
    source+='\nreport; report_rc=$?\n[ "$report_rc" = 2 ] || [ "$report_rc" = 1 ] || exit 99\nscan_diagnostic\n'
    script=d/'test.sh'; script.write_text(source)
    r=subprocess.run(['sh',str(script)],env=dict(os.environ,TEST_DIR=str(d)),capture_output=True,timeout=5)
    self.assertEqual(r.returncode,0,r.stderr.decode())
    self.assertEqual((d/'calls').read_text().splitlines(),['drive','recording']+(['full-info'] if 'contentType' not in rec else []))
    self.assertIn('stage=recording report_rc=',(d/'scan-diagnostic.txt').read_text())
    self.assertLess((d/'scan-diagnostic.txt').stat().st_size,8192)
    self.assertFalse((d/'unexpected-network').exists())
    self.assertEqual(list(p.iterdir()),[])


if __name__ == '__main__': unittest.main()

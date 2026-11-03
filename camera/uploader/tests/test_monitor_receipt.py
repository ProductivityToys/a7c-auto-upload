"""Receipt batches use one frontend, with fresh completion for every step."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

SRC = Path(__file__).resolve().parents[1]


class ReceiptMonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        frontend = cls.root / 'frontend'
        frontend.write_text('''#!/usr/bin/env python3
import os,time
os.read(0,1)
os.write(1,b'Logical  Addr\\nMWF>')
for step in range(2):
 cmd=b''
 while True:
  x=os.read(0,1)
  if not x:raise SystemExit(0)
  if x==b'\\r':break
  cmd+=x
 with open(os.environ['COMMANDS'],'ab') as f:f.write(cmd+b'\\n')
 mode=os.environ['MODE']
 if mode=='die_second' and step==1:raise SystemExit(7)
 # Local echo plus an old prompt cannot advance to the next step.
 os.write(1,cmd+b'\\nMWF>')
 time.sleep(.02)
 if mode=='local_only':raise SystemExit(8)
 body=b"Can't open file x" if mode=='error_'+str(step) else b'OK'
 os.write(1,cmd+b'\\r\\n'+body+b'\\r\\nMWF>')
time.sleep(2)
''')
        frontend.chmod(0o700)
        cls.binary = cls.root / 'monitor'
        subprocess.run(['cc', '-fno-builtin', '-DSD_RECEIPT_MODE',
                        '-DA7C_MONOTONIC_CLOCK=' + str(time.CLOCK_MONOTONIC),
                        '-DA7C_TEST_FRONTEND="' + str(frontend) + '"',
                        str(SRC / 'monitor.c'), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_mode(self, mode, *args):
        calls = self.root / 'calls'
        calls.unlink(missing_ok=True)
        result = subprocess.run([str(self.binary), *args], capture_output=True,
                                env=dict(os.environ, MODE=mode, COMMANDS=str(calls)),
                                timeout=12)
        return result, calls.read_text().splitlines() if calls.exists() else []

    def test_context_is_info_then_root_without_a_second_frontend(self):
        result, calls = self.run_mode('ok', 'context', 'B')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['IFSYS info', 'IFSYS dir B:/'])
        self.assertIn(b'IFSYS info\r\nOK', result.stdout)
        self.assertIn(b'IFSYS dir B:/\r\nOK', result.stdout)

    def test_write_then_readback_is_sequential_and_fixed(self):
        result, calls = self.run_mode('ok', 'write-verify', 'B', 'U123ABCA.RCP')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [
            'IFSYS cp /setting/a7c-uploader/ram/receipt.write B:/U123ABCA.RCP',
            'IFSYS cp B:/U123ABCA.RCP /setting/a7c-uploader/ram/receipt.read'])

    def test_write_error_never_submits_readback(self):
        result, calls = self.run_mode('error_0', 'write-verify', 'B', 'U123ABCA.RCP')
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.stdout, b'')

    def test_failed_or_missing_readback_never_publishes_partial_success(self):
        for mode, rc in [('error_1', 73), ('die_second', 72), ('local_only', 72)]:
            result, calls = self.run_mode(mode, 'write-verify', 'B', 'U123ABCA.RCP')
            self.assertEqual(result.returncode, rc, result.stderr)
            self.assertEqual(result.stdout, b'')
            self.assertEqual(len(calls), 1 if mode == 'local_only' else 2)

    def test_failed_context_does_not_publish_old_card_information(self):
        result, _ = self.run_mode('die_second', 'context', 'B')
        self.assertEqual(result.returncode, 72, result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_receipt_commands_reject_arbitrary_paths_and_filenames(self):
        for args in [('context', '../B'), ('write-verify', 'B', 'C0001.MP4'),
                     ('write-verify', 'B', '../U123ABCA.RCP')]:
            result, calls = self.run_mode('ok', *args)
            self.assertEqual(result.returncode, 64, result.stderr)
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()

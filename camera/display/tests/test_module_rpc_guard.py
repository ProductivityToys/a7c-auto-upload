"""Exercise actual guardian pipe handling, including a killed RPC sender."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class ModuleRpcGuardTests(unittest.TestCase):
    def test_pending_native_request_never_authorizes_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'fixture'
            source = Path(__file__).with_name('module_rpc_guard_fixture.c')
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(source), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS module RPC guardian', result.stdout)


if __name__ == '__main__':
    unittest.main()

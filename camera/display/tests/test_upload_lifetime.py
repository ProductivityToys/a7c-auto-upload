"""Host-only request and independent guardian protocol tests with real pipes."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class UploadLifetimeTests(unittest.TestCase):
    def test_request_and_guardian_faults(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'fixture'
            source=Path(__file__).with_name('upload_lifetime_fixture.c')
            subprocess.run(['cc','-Wall','-Wextra','-Werror',str(source),'-o',str(binary)],check=True)
            result=subprocess.run([str(binary)],cwd=tmp,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS real-pipe guardian',result.stdout)


if __name__=='__main__':unittest.main()

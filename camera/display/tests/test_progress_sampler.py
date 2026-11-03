"""Readonly sampling, bounded lifetime and context-change cleanup."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_progress_sampler import analyze


class ProgressSamplerTests(unittest.TestCase):
    def test_native_rectangle_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/"native-sampler"
            subprocess.run(["cc","-O1","-g","-DNATIVE_RECT_SAMPLE","-fsanitize=address,undefined",str(Path(__file__).with_name("progress_sampler_fixture.c")),"-o",str(binary)],check=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("samples=4000 rc=0",result.stdout)
            self.assertIn("NATIVE_RECT_SAMPLES full=1 nonzero=1",result.stdout)
            self.assertIn("samples=50 rc=69",result.stdout)
            self.assertIn("NATIVE_RECT_GAPS count=2 samples=3 max_samples=2",result.stdout)
            for width,count in ((10,3),(22,1),(46,2)):
                self.assertIn(f"FILL width={width} count={count}",result.stdout)

    def test_readonly_bounds_and_context_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'sampler-fixture'
            subprocess.run(['cc', '-O1', '-g', '-fsanitize=address,undefined',
                            str(Path(__file__).with_name('progress_sampler_fixture.c')),
                            '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('samples=1000 rc=0 unmap=0 close=0,0', result.stdout)
            self.assertIn('samples=50 rc=69 unmap=0 close=0,0', result.stdout)
            first = 'SAMPLER version=2' + result.stdout.split('SAMPLER version=2')[1]
            report = analyze(first)
            self.assertEqual((report['full'], report['blank']), (1, 999))
            self.assertEqual(report['blank_values'], {'0000..0000': 999})
            self.assertEqual(report['controls_while_blank'], {'63': 999})
            self.assertEqual(report['redraw_while_blank'], {'2': 999})
            with self.assertRaises(ValueError):
                analyze(first.replace('R index=100 ', 'R index=101 ', 1))


if __name__ == '__main__':
    unittest.main()

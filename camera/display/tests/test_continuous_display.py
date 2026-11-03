"""Real fork/guardian recovery against synthetic native RAM and font assets."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class ContinuousDisplayTests(unittest.TestCase):
    def test_continuous_visibility_completion_and_crash_recovery(self):
        self.run_fixture(False)

    def test_progress_changes_keep_guardian_recovery(self):
        self.run_fixture(True)

    def test_progress_bar_changes_keep_guardian_recovery(self):
        self.run_fixture("bar")

    def run_fixture(self, progress):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            arrays={'original_font':bytes(range(128)),
                    'replacement_font':bytes(255-i for i in range(128)),
                    'text_marker':bytes([0xa7,0xc0,0,1,0,0,0,0])}
            if progress:
                import sys
                sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
                from dds_small_text_plan import compile_progress_24, compile_progress_bar_24
                arrays['replacement_font'],arrays['text_marker']=(compile_progress_bar_24() if progress=='bar' else compile_progress_24())
            (root/'dds_text_asset.h').write_text(('#define DDS_PROGRESS_EXPERIMENT 1\n' if progress else '')+('#define DDS_PROGRESS_BAR 1\n' if progress=='bar' else '')+'\n'.join(
                'static const unsigned char %s[%d]={%s};'%(name,len(data),','.join(map(str,data)))
                for name,data in arrays.items()))
            binary=root/'fixture'
            subprocess.run(['cc','-O1','-DTEST_DDS_EDGE','-DTEST_DDS_SHOOTING',
                            '-I',str(root),str(Path(__file__).with_name('dds_font_lifecycle_fixture.c')),
                            '-o',str(binary)],check=True)
            result=subprocess.run([str(binary)],cwd=root,capture_output=True,text=True,timeout=80)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS: continuous upload stays visible without interim cleanup',result.stdout)


if __name__=='__main__':unittest.main()

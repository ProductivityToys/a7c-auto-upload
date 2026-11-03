"""Exercise passive sampling and cancellation; never touches a camera."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class FrameObserverTests(unittest.TestCase):
    def test_frame_capture_and_retirement(self):
        for flags in ([], ['-DPRESENT_TRIAL'], ['-DRECT_TRIAL'], ['-DRECT_TRIAL', '-DRECT_SERIES_TRIAL'], ['-DRECT_SERVICE_TRIAL']):
            with self.subTest(flags=flags):
                self.run_fixture('frame_control_host_fixture.c', 'FRAME_CONTROL_OK 15', flags)

    def test_rect_upload_control(self):
        for flags in ([],['-DRECT_SERVICE_TRIAL']):
            with self.subTest(flags=flags),tempfile.TemporaryDirectory() as tmp:
                binary=Path(tmp)/'control'
                source=Path(__file__).with_name('rect_upload_control_fixture.c')
                subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-function',
                                '-fsanitize=address,undefined',*flags,str(source),'-o',str(binary)],check=True)
                result=subprocess.run([str(binary)],cwd=tmp,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('RECT_UPLOAD_CONTROL_OK',result.stdout)

    def test_rect_service(self):
        self.run_fixture('rect_service_fixture.c','RECT_SERVICE_OK')

    def test_rect_service_no_idle(self):
        self.run_fixture('rect_service_fixture.c', 'RECT_SERVICE_OK', ['-DA7C_SERVICE_NO_IDLE'])

    def test_rect_progress(self):
        self.run_fixture('rect_progress_fixture.c', 'RECT_PROGRESS_OK')

    def test_frame_series(self):
        self.run_fixture('frame_series_fixture.c', 'FRAME_SERIES_OK')

    def test_frame_handoff(self):
        self.run_fixture('frame_handoff_fixture.c', 'FRAME_HANDOFF_OK')

    def test_event_handoff(self):
        self.run_fixture('event_handoff_fixture.c', 'EVENT_HANDOFF_OK')

    def test_lifetime_and_sampling(self):
        self.run_fixture('frame_observer_fixture.c', 'FRAME_OBSERVER_OK')

    def run_fixture(self, name, marker, flags=()):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'observer-test'
            source = Path(__file__).with_name(name)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-pthread', *flags, str(source),
                            '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(marker, result.stdout)


if __name__ == '__main__':
    unittest.main()

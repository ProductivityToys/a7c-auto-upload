"""Exercise the temporary shell trial with a fake sysfs node and real processes."""
from pathlib import Path
import os
import signal
import subprocess
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'usb_softlink_trial.sh'


class SoftlinkTrialTests(unittest.TestCase):
    def run_case(self, cancel=False, kill_writer=False):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)
            (p / 'state').write_text('configured\n')
            (p / 'node').write_text('')
            if cancel:
                (p / 'cancel').touch()
            # Substitute only the fixed hardware environment and shorten time.
            text = SOURCE.read_text().replace('B=/bin/busybox', 'B=')
            text = text.replace('D=/setting/a7c-debug/ram/usb-softlink', 'D=' + root)
            text = text.replace('NODE=/sys/class/udc/dwc3.0/soft_connect', 'NODE=' + str(p / 'node'))
            text = text.replace('STATE=/sys/class/udc/dwc3.0/state', 'STATE=' + str(p / 'state'))
            text = text.replace("$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90", ':')
            text = text.replace('DELAY=60', 'DELAY=.1').replace('RESTORE=90', 'RESTORE=1.5')
            text = text.replace('$B sleep 1', '$B sleep .01').replace('$B sleep 2', '$B sleep .02')
            script = p / 'trial.sh'
            script.write_text(text)
            process = subprocess.Popen(['sh', str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                if kill_writer:
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline and (p / 'node').read_text() != 'disconnect\n':
                        time.sleep(.01)
                    self.assertEqual((p / 'node').read_text(), 'disconnect\n')
                    os.kill(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not (p / 'finished').exists():
                    time.sleep(.02)
                self.assertTrue((p / 'finished').exists())
                self.assertEqual((p / 'node').read_text(), '' if cancel else 'connect\n')
                log = (p / 'events.log').read_text()
                self.assertIn('TRIAL_CANCELLED' if cancel else 'RECONNECT_RETURN rc=0', log)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_disconnect_then_reconnect(self):
        self.run_case()

    def test_cancel_before_disconnect_makes_no_sysfs_write(self):
        self.run_case(cancel=True)

    def test_reconnect_survives_writer_sigkill(self):
        self.run_case(kill_writer=True)


if __name__ == '__main__':
    unittest.main()

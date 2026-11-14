"""Run the production health shell against local stand-ins, without USB."""
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a7c_installer.transport.sony_usb import SonyUsb


@unittest.skipIf(os.name == 'nt', 'POSIX health shell; executed on macOS')
class HealthDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ram = self.root / 'ram'
        self.native = self.root / 'dds/native-service'
        self.ram.mkdir()
        self.native.mkdir(parents=True)
        (self.root / 'display').mkdir()
        (self.root / 'display/enabled').touch()
        (self.ram / 'plain.worker.pid').write_text('42\n')
        (self.ram / 'plain-boot-timings.log').write_text('op=worker_exec ready\n')
        (self.native / 'owner').write_text('42\n')
        (self.native / 'im.pid').write_text('123\n')
        (self.native.parent / 'native-start.log').write_text('NATIVE_SERVICE_READY\n')
        self.executable(self.root / 'bb', '#!/bin/sh\n'
                        'case "$1" in pidof) echo 123;; sleep) sleep .02;; *) exec "$@";; esac\n')
        camera = SonyUsb()
        with patch.object(camera, 'command', return_value='UPLOAD=ready\nDISPLAY=ready') as command:
            camera.service_health('RUNNING:41:42')
        self.script = command.call_args.args[0]
        for source, target in [('/bin/busybox', self.root / 'bb'),
                               ('/setting/a7c-uploader/ram', self.ram),
                               ('/setting/a7c-debug/ram/dds-once/native-service', self.native),
                               ('/setting/a7c-display', self.root / 'display'),
                               ('/proc/', str(self.root / 'proc') + '/')]:
            self.script = self.script.replace(source, str(target))

    def executable(self, path, body):
        path.write_text(body)
        path.chmod(0o700)

    def run_health(self):
        return subprocess.run(['sh', '-c', self.script], text=True, capture_output=True,
                              timeout=3, check=True).stdout

    def test_ready_and_failed_probe_results_and_pid_cleanup(self):
        for code, result in [(0, 'ready'), (1, 'error')]:
            with self.subTest(code=code):
                self.executable(self.native / 'probe', f'#!/bin/sh\nexit {code}\n')
                self.assertIn('DISPLAY=' + result, self.run_health())
                self.assertFalse((self.ram / 'display-health.pid').exists())

    def test_term_ignoring_probe_does_not_hold_the_usb_response(self):
        self.executable(self.native / 'probe', f'#!{sys.executable}\n'
                        'import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(60)\n')
        start = time.monotonic()
        self.assertIn('DISPLAY=starting', self.run_health())
        self.assertLess(time.monotonic() - start, 3)
        # The timeout path retains the PID so a still-pending kernel read does
        # not create a new probe on every subsequent health check.
        self.assertTrue((self.ram / 'display-health.pid').read_text().strip().isdigit())

    def test_pending_probe_is_not_repeated_and_stale_pid_can_retry(self):
        previous = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
        try:
            (self.ram / 'display-health.pid').write_text(str(previous.pid))
            proc = self.root / 'proc' / str(previous.pid)
            proc.mkdir(parents=True)
            (proc / 'cmdline').write_text(str(self.native / 'probe') + '\0--inspect-service\0')
            started = self.root / 'started'
            self.executable(self.native / 'probe', '#!/bin/sh\ntouch ' + shlex.quote(str(started)) + '\n')
            self.assertIn('DISPLAY=starting', self.run_health())
            self.assertFalse(started.exists())
            # A reused PID belonging to a different program must not suppress
            # the next probe or receive a signal from the health check.
            (proc / 'cmdline').write_text('unrelated-program\0')
            self.assertIn('DISPLAY=ready', self.run_health())
            self.assertTrue(started.exists())
            self.assertIsNone(previous.poll())
        finally:
            previous.send_signal(signal.SIGKILL)
            previous.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()

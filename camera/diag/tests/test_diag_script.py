"""diag.sh reports fixed files only and never leaks secrets."""
from pathlib import Path
import subprocess, tempfile, unittest

SRC = Path(__file__).resolve().parents[1]
SECRET, TOKEN = 'S3cret-ftp-pass', 'ef' * 32


class DiagScriptTests(unittest.TestCase):
    def run_diag(self, verb, ftp_rc=0, config=True):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            u, r, c, p = t / 'setting/a7c-uploader', t / 'setting/a7c-uploader/ram', t / 'setting/a7c-uploader/plainftp', t / 'setting/a7c-diag'
            for d in (r / 'diag', c, p):
                d.mkdir(parents=True)
            (p / 'token').write_text(TOKEN + '\n')
            if config:
                (c / 'config').write_text('a7c-plainftp-v2\n192.168.5.190\n21\na7c-upload\n/\n1\n')
            (c / 'password').write_text(SECRET + '\n')
            (u / 'installed.json').write_text('{\n  "version": "0.4.2-photos.7-preview"\n}\n')
            (u / 'enabled').write_text('x')
            (r / 'events.log').write_text('FTP_HEALTH healthy 1.0 2.0\n')
            (r / 'ftp-health').write_text('healthy\n')
            client = r / 'plainftp'
            client.write_text(f'#!/bin/sh\nread pw\necho "$1 $2 $3 $4 $5 $pw" > "{t}/client-args"\nexit {ftp_rc}\n')
            client.chmod(0o700)
            bb = t / 'bb'
            bb.write_text('#!/bin/sh\nif [ "$1" = ping ]; then echo "64 bytes: time=3.1 ms"; exit 0; fi\nexec "$@"\n')
            bb.chmod(0o700)
            script = (SRC / 'diag.sh').read_text().replace('B=/bin/busybox', f'B={bb}').replace('/setting/', f'{t}/setting/')
            p = subprocess.run(['sh', '-s', verb], input=script, capture_output=True, text=True, timeout=10)
            args = (t / 'client-args').read_text() if (t / 'client-args').exists() else ''
            probe = (r / 'diag/probe.txt').read_text() if (r / 'diag/probe.txt').exists() else ''
            return p.returncode, p.stdout + p.stderr, args, probe

    def test_status_reports_versions_health_and_logs_without_secrets(self):
        rc, out, _, _ = self.run_diag('STATUS')
        self.assertEqual(rc, 0, out)
        for text in ('A7C_DIAG_V1', 'installed=0.4.2-photos.7-preview', 'photos=1', 'ftp_health=healthy', 'FTP_HEALTH healthy', 'A7C_DIAG_END'):
            self.assertIn(text, out)
        self.assertNotIn(SECRET, out); self.assertNotIn(TOKEN, out)

    def test_trace_reports_bounded_logs(self):
        rc, out, _, _ = self.run_diag('TRACE')
        self.assertEqual(rc, 0, out)
        self.assertIn('== events (', out)
        self.assertNotIn(SECRET, out)

    def test_probe_passes_password_on_stdin_only_and_records_result(self):
        for ftp_rc in (0, 75):
            rc, out, args, probe = self.run_diag('PROBE', ftp_rc)
            self.assertEqual(rc, 0, out)
            self.assertEqual(args.split(), ['check', '192.168.5.190', '21', 'a7c-upload', '/', SECRET])
            self.assertIn(f'probe_ftp target=192.168.5.190:21 rc={ftp_rc} ', probe)
            self.assertIn('probe_ping ok time=3.1 ms', probe)
            self.assertIn('== last_probe', out)
            self.assertNotIn(SECRET, out + probe)

    def test_probe_without_config_and_unknown_verb(self):
        rc, out, args, probe = self.run_diag('PROBE', config=False)
        self.assertEqual((rc, args, probe.strip()), (3, '', 'probe=no_config'))
        self.assertEqual(self.run_diag('SHELL')[0], 64)


    def test_start_requires_installed_supervisor(self):
        rc, out, _, _ = self.run_diag('START')
        self.assertEqual(rc, 3, out)
        self.assertIn('start=disabled', out)


class LoadTests(unittest.TestCase):
    def test_status_reports_cpu_ticks_for_own_and_native_processes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp); r = t / 'setting/a7c-uploader/ram'; (r / 'diag').mkdir(parents=True)
            proc = t / 'proc'; (proc / 'net').mkdir(parents=True)
            (proc / 'uptime').write_text('100.50 300.00\n'); (proc / 'loadavg').write_text('0.10 0.20 0.30 1/80 900\n')
            (proc / 'stat').write_text('cpu  10 0 20 900 5 0 1 0 0 0\ncpu0 10 0 20 900 5 0 1 0 0 0\nintr 1\n')
            for pid, comm in ((41, 'ash'), (42, 'my (odd) name'), (162, 'im.elf')):
                (proc / str(pid)).mkdir()
                fields = ['S'] + ['0'] * 10 + ['7', '8', '9', '10'] + ['0'] * 30
                (proc / str(pid) / 'stat').write_text(f'{pid} ({comm}) ' + ' '.join(fields) + '\n')
            (r / 'supervisor.pid').write_text('41\n'); (r / 'plain.worker.pid').write_text('42\n')
            bb = t / 'bb'; bb.write_text('#!/bin/sh\n[ "$1" != pidof ] || { echo 162; exit 0; }\nexec "$@"\n'); bb.chmod(0o700)
            script = (SRC / 'diag.sh').read_text().replace('B=/bin/busybox', f'B={bb}').replace('/setting/', f'{t}/setting/').replace('/proc/', f'{t}/proc/')
            out = subprocess.run(['sh', '-s', 'STATUS'], input=script, capture_output=True, text=True, timeout=10).stdout
            self.assertIn('== load', out); self.assertIn('cpu  10 0 20 900', out)
            self.assertIn('proc supervisor pid=41 utime=7 stime=8 cutime=9 cstime=10', out)
            self.assertIn('proc worker pid=42 utime=7 stime=8 cutime=9 cstime=10', out)
            self.assertIn('proc im pid=162 utime=7 stime=8 cutime=9 cstime=10', out)


class StartGuardTests(unittest.TestCase):
    def test_busy_or_disabled_is_refused(self):
        import tempfile
        for make, expected in (('lock', 2), ('source.fifo', 2), (None, 3), ('idle', 0)):
            with tempfile.TemporaryDirectory() as tmp:
                t = Path(tmp); u = t / 'setting/a7c-uploader'; r = u / 'ram'
                (r / 'diag').mkdir(parents=True)
                if make:
                    (u / 'enabled').write_text('x'); (u / 'supervisor.sh').write_text('touch "$0.started"\n')
                    if make == 'lock': (r / make).mkdir()
                    elif make != 'idle': (r / make).write_text('')
                bb = t / 'bb'; bb.write_text('#!/bin/sh\nexec "$@"\n'); bb.chmod(0o700)
                script = (SRC / 'diag.sh').read_text().replace('B=/bin/busybox', f'B={bb}').replace('/setting/', f'{t}/setting/').replace('/bin/ash', '/bin/sh')
                p = subprocess.run(['sh', '-s', 'START'], input=script, capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, expected, p.stdout)
                if expected == 0: self.assertIn('start=requested', p.stdout)
                self.assertEqual((u / 'supervisor.sh.started').exists(), expected == 0)


if __name__ == '__main__':
    unittest.main()

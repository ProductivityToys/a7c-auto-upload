"""Exercise trial sequencing with subprocesses; no camera or native calls."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'module/ablation_trial.sh'
PHASES = ['--service-ready', '--service-on', '--inspect-service',
          '--service-preview', '--service-off', '--finish-event', '--inspect-marker']


class AblationTrialTests(unittest.TestCase):
    def run_case(self, fail='', code=88, enabled=False, ready=True, retain=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d, u, n = (root / x for x in ('maint', 'upload', 'frames'))
            for p in (d, u, n): p.mkdir()
            (root/'boot').write_text('test-boot\n')
            (d/'boot-id').write_text('test-boot\n')
            (u/'worker.pid').write_text(str(os.getpid())+'\n')
            (root/'mounts').write_text('a7c-debug-ram /setting/a7c-debug/ram tmpfs rw 0 0\nnone /tmp_bt tmpfs rw 0 0\n')
            flag=root/'enabled'
            if enabled: flag.touch()
            shim=root/'busybox'
            shim.write_text('#!/bin/sh\ncase "$1" in pidof) echo 42;; *) exec "$@";; esac\n')
            shim.chmod(0o700)
            probe=d/'probe'
            probe.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "'+str(d/'calls')+'"\n'
                             + (f'[ "$1" != "{fail}" ] || exit {code}\n' if fail else '')+'exit 0\n')
            probe.chmod(0o700)
            lease=d/'lease'
            lease.write_text('#!/bin/sh\n'+(f'touch "{d}/lease.ready"\n' if ready else 'exit 69\n')+
                             f'while [ ! -e "{d}/lease.done" ]; do sleep 0.05; done\necho GUARD_RELEASED\n')
            lease.chmod(0o700)
            script=root/'trial'
            text=SOURCE.read_text().replace('B=/bin/busybox',f'B={shim}')
            for old,new in [('D=/setting/a7c-debug/ram/maint',f'D={d}'),
                            ('U=/setting/a7c-uploader/ram',f'U={u}'),
                            ('N=/setting/a7c-debug/ram/dds-once/native-service',f'N={n}'),
                            ('/proc/sys/kernel/random/boot_id',str(root/'boot')),
                            ('/proc/mounts',str(root/'mounts')),
                            ('/setting/a7c-display/enabled',str(flag))]:
                text=text.replace(old,new)
            script.write_text(text)
            args=['sh',str(script)]+(['--retain-service'] if retain else [])
            result=subprocess.run(args,capture_output=True,text=True,timeout=10)
            calls=(d/'calls').read_text().splitlines() if (d/'calls').exists() else []
            if enabled:
                self.assertEqual(result.returncode,92)
                self.assertFalse((d/'trial.claim').exists())
                self.assertEqual(calls,[])
                return
            if not ready:
                self.assertEqual(result.returncode,96)
                self.assertEqual(calls,[])
                return
            self.assertEqual(result.returncode,code if fail else 0,result.stdout+result.stderr)
            self.assertEqual(calls,PHASES[:PHASES.index(fail)+1] if fail else PHASES[:4] if retain else PHASES)
            self.assertIn('GUARD_RELEASED',result.stdout)
            self.assertEqual('ABLATION_RESTORED' in result.stdout,not fail and not retain)
            self.assertEqual('ABLATION_RETAINED_SERVICE' in result.stdout,not fail and retain)
            second=subprocess.run(args,capture_output=True,text=True,timeout=5)
            self.assertEqual(second.returncode,93)
            self.assertEqual((d/'calls').read_text().splitlines(),calls)

    def test_success_and_no_repeat(self): self.run_case()
    def test_explicit_retained_trial_releases_lease_without_unload(self): self.run_case(retain=True)
    def test_each_failed_phase_stops_before_next_native_operation(self):
        for phase in PHASES:
            with self.subTest(phase=phase): self.run_case(fail=phase)
    def test_terminated_probe_not_followed_by_cleanup(self): self.run_case(fail='--service-on',code=143)
    def test_display_enabled_rejected(self): self.run_case(enabled=True)
    def test_lease_failure_never_loads(self): self.run_case(ready=False)


if __name__ == '__main__': unittest.main()

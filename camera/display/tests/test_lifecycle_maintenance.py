"""Temporary maintenance protocol regression; no camera access."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / 'module'


class LifecycleMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = r = Path(self.tmp.name)
        self.d = d = r/'maint'; d.mkdir()
        (r/'upload').mkdir()
        (r/'boot').write_text('boot-test\n')
        (d/'boot-id').write_text('boot-test\n')
        (r/'mounts').write_text('a7c-debug-ram /setting/a7c-debug/ram tmpfs rw 0 0\n')
        bb = r/'bb'
        bb.write_text('#!/bin/sh\ncase "$1" in pidof) echo 42;; *) exec "$@";; esac\n')
        bb.chmod(0o700)
        for name in ('action', 'manage'):
            text = (SRC/f'lifecycle_{name}.sh').read_text()
            for old, new in [('B=/bin/busybox', f'B={bb}'),
                             ('/setting/a7c-debug/ram/maint', str(d)),
                             ('/setting/a7c-uploader/ram', str(r/'upload')),
                             ('/setting/a7c-display/enabled', str(r/'enabled')),
                             ('/proc/mounts', str(r/'mounts')),
                             ('/proc/sys/kernel/random/boot_id', str(r/'boot')),
                             ('/bin/ash', '/bin/sh')]:
                text = text.replace(old, new)
            (r/name).write_text(text)
        probe = d/'probe'
        probe.write_text('#!/bin/sh\necho "$1" >> "'+str(d/'calls')+'"\n'
                         'echo MODULE_IM_PENDING inact=0 act=0\n'
                         'case "$1" in --inspect-frame) echo FRAME_SOURCE_REJECT stage=manager-state; exit 87;; esac\n')
        probe.chmod(0o700)

    def run_script(self, script, *args):
        return subprocess.run(['sh', str(self.root/script), *args], capture_output=True, text=True, timeout=5)

    def terminal(self, state):
        (self.d/'trial.claim').mkdir()
        (self.d/'trial.state').write_text(state+'\n')

    def test_probe_survives_subsequent_status_and_retains_failure_detail(self):
        self.assertEqual(self.run_script('action', 'PROBE').returncode, 0)
        result = self.run_script('action', 'STATUS')
        self.assertIn('MODULE_IM_PENDING inact=0 act=0', result.stdout)
        self.assertIn('FRAME_SOURCE_REJECT stage=manager-state', result.stdout)
        self.assertIn('PROBE_DONE service_rc=0 frame_rc=87', result.stdout)
        self.assertIn('boot-test', result.stdout)

    def test_known_early_preview_failure_can_retire(self):
        self.terminal('ABLATION_END rc=87 phase=--service-preview')
        self.assertEqual(self.run_script('action', 'PAUSE').returncode, 0)
        self.assertEqual((self.d/'calls').read_text().splitlines(),
                         ['--inspect-service', '--service-off', '--finish-event', '--inspect-marker'])
        self.assertEqual((self.d/'trial.state').read_text(), 'LIFECYCLE_REVOKED\n')
        self.assertTrue((self.d/'trial.claim').is_dir())

    def test_unknown_load_outcome_does_not_auto_retire(self):
        self.terminal('ABLATION_END rc=143 phase=--service-on')
        self.assertEqual(self.run_script('action', 'PAUSE').returncode, 92)
        self.assertFalse((self.d/'calls').exists())

    def test_completed_trial_allows_external_updates_without_rearming(self):
        self.terminal('ABLATION_END rc=87 phase=--service-preview')
        self.assertEqual(self.run_script('manage', 'XLOCK').returncode, 0)
        (self.d/'incoming').write_text('#!/bin/sh\nexit 0\n')
        self.assertEqual(self.run_script('manage', 'XCOMMIT', 'action:17:hash').returncode, 0)
        self.assertTrue((self.d/'action.sh').exists())
        self.assertFalse((self.d/'trial.sh').exists())
        self.assertTrue((self.d/'trial.claim').is_dir())
        self.assertEqual(self.run_script('action', 'START').returncode, 93)

    def test_in_progress_trial_blocks_update(self):
        self.terminal('ABLATION_PHASE_BEGIN --service-preview')
        self.assertNotEqual(self.run_script('manage', 'XLOCK').returncode, 0)
        self.assertFalse((self.d/'transfer.lock').exists())

    def test_module_and_startup_not_update_targets(self):
        self.assertEqual(self.run_script('manage', 'XLOCK').returncode, 0)
        (self.d/'incoming').write_bytes(b'payload')
        for role in ('module', 'startup', 'trial'):
            self.assertEqual(self.run_script('manage', 'XCOMMIT', role+':7:hash').returncode, 64)
        self.assertTrue((self.d/'incoming').exists())

    def test_stale_boot_cannot_query_or_mutate(self):
        (self.d/'boot-id').write_text('other-boot\n')
        self.assertEqual(self.run_script('action', 'PROBE').returncode, 91)
        self.assertFalse((self.d/'calls').exists())


if __name__ == '__main__': unittest.main()

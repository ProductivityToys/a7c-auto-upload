"""Exercise shell dispatch with fake proc/RAM and a recording display binary."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "dds_wireless_action.sh"


class DDSWirelessActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.d = self.root / "ram/dds-once"
        self.d.mkdir(parents=True)
        (self.root / "mounts").write_text(f"a7c-debug-ram {self.root}/ram tmpfs rw\n")
        (self.root / "boot").write_text("same-boot\n")
        (self.root / "uptime").write_text("123.45 0\n")
        (self.root / "proc/162").mkdir(parents=True)
        (self.root / "proc/162/maps").write_text("14cee000-14d84000 rw-s fe33a000 00:01 2 /dev/example\n")
        for n, v in (("boot-id", "same-boot"), ("native.pid", "162"), ("native.base", "6015000"),
                     ("native.mode", "--once-idle"), ("native.timer", "239")):
            (self.d / n).write_text(v + "\n")
        bb = self.root / "bb"
        bb.write_text("#!/bin/sh\nif [ \"$1\" = head ]; then echo 'applet not found' >&2; exit 127; "
                      "elif [ \"$1\" = pidof ]; then echo 162; "
                      "elif [ \"$1\" = timeout ]; then shift 5; exec \"$@\"; else exec \"$@\"; fi\n")
        bb.chmod(0o700)
        capture = self.d / "capture"
        capture.write_text("#!/bin/sh\necho \"$*\" >> '" + str(self.root / "calls") + "'\n"
                           f"if [ -f '{self.root}/fail' ]; then exit 91; fi\n"
                           f"cat '{self.root}/native-state'\necho DDS_MOCK_OK\n")
        (self.root / "native-state").write_text("DDS_STATE attached timer=239 first=0 override=0 visible=0 others_idle=1\n")
        capture.chmod(0o700)
        script = SOURCE.read_text()
        for a, b in (("B=/bin/busybox", f"B={bb}"),
                     ("/setting/a7c-debug/ram", str(self.root / "ram")),
                     ("/proc/mounts", str(self.root / "mounts")),
                     ("/proc/sys/kernel/random/boot_id", str(self.root / "boot")),
                     ("/proc/uptime", str(self.root / "uptime"))):
            script = script.replace(a, b)
        script = script.replace('/proc/$p/maps', str(self.root / 'proc') + '/$p/maps')
        script = script.replace('/usr/bin/ulogio', str(self.root / 'ulogio'))
        self.action = self.root / "action.sh"
        self.action.write_text(script)

    def tearDown(self):
        self.tmp.cleanup()

    def run_action(self, verb):
        return subprocess.run(["sh", str(self.action), verb], capture_output=True, text=True, timeout=3)

    def test_success_once_and_status_does_not_repeat(self):
        self.assertEqual(self.run_action("PROBE").returncode, 0)
        calls = (self.root / "calls").read_text()
        self.assertEqual(calls.splitlines(), ["--inspect 162 6015000", "--once-idle 162 6015000", "--inspect 162 6015000"])
        self.assertEqual(self.run_action("PROBE").returncode, 92)
        status = self.run_action("STATUS")
        self.assertIn("stage=restored", status.stdout)
        self.assertTrue(status.stdout.endswith("A7C_DEBUG_END\n"))
        self.assertEqual((self.root / "calls").read_text(), calls)
        self.assertIn("/dev/example", status.stdout)

    def test_status_does_not_read_maps_after_boot_change(self):
        (self.root / "boot").write_text("new-boot\n")
        status = self.run_action("STATUS")
        self.assertIn("CURRENT_SHARED_MAPS_UNAVAILABLE", status.stdout)
        self.assertNotIn("/dev/example", status.stdout)
        self.assertFalse((self.root / "calls").exists())

    def test_status_maps_bounded_without_head_applet(self):
        line = "14cee000-14d84000 rw-s fe33a000 00:01 2 /dev/example\n"
        (self.root / "proc/162/maps").write_text(line * 1000)
        status = self.run_action("STATUS")
        maps = status.stdout.split("CURRENT_SHARED_MAPS_LIMIT_BYTES=12000\n")[1]
        self.assertEqual(maps, (line * 1000)[:12000] + "\nA7C_DEBUG_END\n")
        self.assertNotIn("applet not found", status.stderr)

    def test_layout_diagnosis_never_invokes_display(self):
        self.prepare_layout_diagnosis()
        self.assertEqual(self.run_action("PROBE").returncode, 0)
        self.assertEqual(self.run_action("PROBE").returncode, 92)
        self.assertFalse((self.root / "calls").exists())
        self.assertEqual((self.root / "layout-calls").read_text(), "queried\n")
        self.assertIn("stage=diagnosed", self.run_action("STATUS").stdout)

    def prepare_layout_diagnosis(self):
        (self.d / "diagnose-only").touch()
        layout = self.d / "ui-layout"
        layout.write_text(f"#!/bin/sh\necho queried >> '{self.root}/layout-calls'\n")
        layout.chmod(0o700)
        log = self.root / "ulogio"
        log.write_text("#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n"
                       "Path(sys.argv[4]).write_bytes(b'groupID: 1 layoutID: 2\\n'.ljust(32768,b'\\n'))\n")
        log.chmod(0o700)

    def test_optional_shooting_capture_never_uses_display_command(self):
        self.prepare_layout_diagnosis()
        (self.d / "capture-only").touch()
        self.assertEqual(self.run_action("PROBE").returncode, 0)
        self.assertEqual((self.root / "calls").read_text(), "--capture-shooting 162 6015000\n")
        self.assertEqual(self.run_action("PROBE").returncode, 92)
        self.assertIn("stage=captured", self.run_action("STATUS").stdout)

    def test_shooting_capture_failure_preserves_diagnostics_without_display(self):
        self.prepare_layout_diagnosis()
        (self.d / "capture-only").touch()
        (self.root / "fail").touch()
        self.assertEqual(self.run_action("PROBE").returncode, 96)
        self.assertEqual((self.d / "shooting.rc").read_text(), "91\n")
        self.assertEqual((self.root / "calls").read_text(), "--capture-shooting 162 6015000\n")
        self.assertEqual(self.run_action("PROBE").returncode, 92)

    def test_physical_capture_is_explicit_readonly_command(self):
        self.prepare_layout_diagnosis()
        (self.d / "capture-only").touch()
        (self.d / "physical-only").touch()
        self.assertEqual(self.run_action("PROBE").returncode, 0)
        self.assertEqual((self.root / "calls").read_text(), "--capture-physical 162 6015000\n")
        self.assertEqual(self.run_action("PROBE").returncode, 92)

    def test_changed_boot_consumes_claim_without_display(self):
        (self.root / "boot").write_text("new-boot\n")
        self.assertEqual(self.run_action("PROBE").returncode, 95)
        self.assertEqual(self.run_action("PROBE").returncode, 92)
        self.assertFalse((self.root / "calls").exists())

    def prepare_retry(self, log=None):
        self.prepare_layout_diagnosis()
        for name in ('diagnose-only', 'capture-only', 'physical-only', 'retry-readonly'):
            (self.d / name).write_text('1\n')
        if log is None:
            log = 'DDS_CAPTURE_REJECT physical_required matches=0 pixel_read_started=0'
        (self.root / 'mock-log').write_text(log + '\n')
        (self.d / 'capture').write_text(
            f'#!/bin/sh\necho "$*" >> "{self.root}/calls"\n'
            f'cat "{self.root}/mock-log"\nexit 84\n')

    def test_readonly_mapping_mismatch_allows_only_three_manual_attempts(self):
        self.prepare_retry()
        for count in range(1, 4):
            self.assertEqual(self.run_action('PROBE').returncode, 96)
            self.assertEqual((self.d / 'capture-attempts').read_text(), f'{count}\n')
            self.assertEqual((self.d / 'claimed').exists(), count == 3)
        self.assertEqual(self.run_action('PROBE').returncode, 92)
        self.assertEqual((self.root / 'calls').read_text().splitlines(),
                         ['--capture-physical 162 6015000'] * 3)

    def test_readonly_retry_requires_all_markers_and_no_prior_output(self):
        for invalid in ('physical-only', 'overlay.log', 'shooting.raw'):
            with self.subTest(invalid=invalid):
                self.prepare_retry()
                if invalid == 'physical-only':
                    (self.d / invalid).unlink()
                else:
                    (self.d / invalid).write_text('preserve')
                self.assertEqual(self.run_action('PROBE').returncode, 95)
                self.assertFalse((self.root / 'calls').exists())
                (self.d / 'claimed').rmdir()
                (self.d / invalid).unlink(missing_ok=True)

    def test_readonly_ambiguous_failure_never_releases_claim(self):
        self.prepare_retry('DDS_PHYSICAL copied=614400 unmap=0 close=0 errno=0\n'
                           'DDS_CAPTURE_REJECT physical_required matches=0 pixel_read_started=0')
        self.assertEqual(self.run_action('PROBE').returncode, 96)
        self.assertEqual(self.run_action('PROBE').returncode, 92)

    def test_readonly_success_after_mismatch_locks_claim(self):
        self.prepare_retry()
        self.assertEqual(self.run_action('PROBE').returncode, 96)
        (self.d / 'capture').write_text(f'#!/bin/sh\necho pixels > "{self.d}/shooting.raw"\n')
        self.assertEqual(self.run_action('PROBE').returncode, 0)
        self.assertEqual(self.run_action('PROBE').returncode, 92)
        self.assertEqual((self.d / 'shooting.raw').read_text(), 'pixels\n')

    def test_shooting_display_queries_layout_then_runs_once(self):
        self.prepare_layout_diagnosis()
        (self.d / 'diagnose-only').unlink()
        (self.d / 'shooting-overlay').write_text('1\n')
        (self.d / 'native.mode').write_text('--once-shooting-idle\n')
        self.assertEqual(self.run_action('PROBE').returncode, 0)
        self.assertEqual((self.root / 'layout-calls').read_text(), 'queried\n')
        self.assertEqual((self.root / 'calls').read_text().splitlines(),
                         ['--inspect 162 6015000', '--once-shooting-idle 162 6015000', '--inspect 162 6015000'])
        self.assertEqual(self.run_action('PROBE').returncode, 92)

    def test_shooting_display_refuses_missing_or_mixed_markers(self):
        (self.d / 'native.mode').write_text('--once-shooting-idle\n')
        self.assertEqual(self.run_action('PROBE').returncode, 95)
        (self.d / 'claimed').rmdir()
        self.prepare_retry()
        (self.d / 'shooting-overlay').write_text('1\n')
        self.assertEqual(self.run_action('PROBE').returncode, 95)
        self.assertFalse((self.root / 'calls').exists())

    def prepare_blink(self, fault=''):
        self.prepare_layout_diagnosis()
        (self.d / 'diagnose-only').unlink()
        (self.d / 'shooting-overlay').write_text('1\n')
        (self.d / 'blink').write_text('4\n')
        (self.d / 'native.mode').write_text('--once-shooting-idle\n')
        (self.d / 'capture').write_text(
            '#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n'
            f'd=Path({str(self.d)!r}); fault={fault!r}\n'
            f'with Path({str(self.root / "calls")!r}).open("a") as f: f.write(" ".join(sys.argv[1:])+"\\n")\n'
            'count=int((d/"mock-count").read_text()) if (d/"mock-count").exists() else 0\n'
            'if sys.argv[1]=="--inspect":\n'
            ' print("DDS_STATE attached timer=239 first=0 override=0 visible=0 others_idle=1")\n'
            ' print("DDS_FONT original_matches=1 bytes=128")\n'
            ' if not (fault=="restore" and count==2): print("DDS_POSITION original_matches=1 x=30 y=250")\n'
            'else:\n'
            ' count+=1; (d/"mock-count").write_text(str(count))\n'
            ' for phase in ("before","during","late","after"):\n'
            '  with (d/("dds-"+phase+".raw")).open("xb") as f: f.write(bytes([count])*614400)\n'
            ' if count==2 and fault=="exit": sys.exit(91)\n'
            ' if count==2 and fault=="cancel": (d/"cancel").touch()\n'
            ' if count==2 and fault=="short": (d/"dds-after.raw").write_bytes(b"short")\n'
            ' print("DDS_DONE display=0 cleanup=0 guardian=0 captures=0,0,0")\n')

    def test_blink_four_successful_transactions_keep_first_and_final_frames(self):
        self.prepare_blink()
        self.assertEqual(self.run_action('PROBE').returncode, 0)
        self.assertEqual((self.d / 'mock-count').read_text(), '4')
        self.assertEqual((self.d / 'dds-first.raw').read_bytes(), bytes([1])*614400)
        for phase in ('before', 'during', 'late', 'after'):
            self.assertEqual((self.d / f'dds-{phase}.raw').read_bytes(), bytes([4])*614400)
        self.assertEqual((self.d / 'overlay.log').read_text().count('DDS_BLINK cycle='), 4)
        self.assertEqual(self.run_action('PROBE').returncode, 92)

    def test_blink_stops_on_failure_or_cancel_and_preserves_failed_evidence(self):
        for fault, code in [('exit', 97), ('restore', 98), ('short', 98), ('cancel', 94)]:
            with self.subTest(fault=fault):
                self.prepare_blink(fault)
                self.assertEqual(self.run_action('PROBE').returncode, code)
                self.assertEqual((self.d / 'mock-count').read_text(), '2')
                self.assertTrue((self.d / 'dds-after.raw').exists())
                self.assertFalse((self.d / 'prewrite-abort').exists())
                self.assertEqual(self.run_action('PROBE').returncode, 94 if fault == 'cancel' else 92)
                for name in ('mock-count', 'overlay.log', 'cancel', 'dds-first.raw',
                             'dds-before.raw', 'dds-during.raw', 'dds-late.raw', 'dds-after.raw'):
                    (self.d / name).unlink(missing_ok=True)
                (self.d / 'claimed').rmdir()

    def test_blink_refuses_unbounded_count_and_legacy_mode(self):
        (self.d / 'blink').write_text('4\n')
        self.assertEqual(self.run_action('PROBE').returncode, 95)
        (self.d / 'claimed').rmdir()
        self.prepare_blink()
        (self.d / 'blink').write_text('999\n')
        self.assertEqual(self.run_action('PROBE').returncode, 95)
        self.assertFalse((self.root / 'calls').exists())

    def prepare_continuous(self, fault='cancel'):
        self.prepare_blink(fault)
        (self.d / 'blink').unlink()
        (self.d / 'continuous-blink').write_text('300\n')
        launch = self.d / 'blink-launch'
        launch.write_text(f'#!/bin/sh\necho launched > "{self.d}/mock-launch"\n')
        launch.chmod(0o700)

    def test_continuous_launch_returns_without_drawing_then_worker_stops_on_cancel(self):
        self.prepare_continuous()
        self.assertEqual(self.run_action('PROBE').returncode, 0)
        self.assertTrue((self.d / 'mock-launch').exists())
        self.assertFalse((self.root / 'calls').exists())
        self.assertEqual(self.run_action('PROBE').returncode, 92)
        self.assertEqual(self.run_action('RUN').returncode, 0)
        self.assertEqual((self.d / 'mock-count').read_text(), '2')
        self.assertEqual((self.d / 'blink-stop').read_text(), 'reason=cancel\n')
        self.assertEqual((self.d / 'blink-history').read_text().splitlines(),
                         ['cycle=1 restored=1', 'cycle=2 restored=1'])
        self.assertTrue((self.d / 'dds-after.raw').exists())
        self.assertEqual((self.d / 'overlay.log').read_text().count('DDS_BLINK cycle='), 1)
        self.assertFalse((self.d / 'blink-worker.running').exists())
        (self.d / 'cancel').unlink()
        self.assertEqual(self.run_action('RUN').returncode, 92)

    def test_continuous_deadline_preserves_last_success_and_private_run_needs_claim(self):
        self.prepare_continuous('')
        self.assertEqual(self.run_action('RUN').returncode, 95)
        capture = self.d / 'capture'
        text = capture.read_text().replace(
            'count+=1; (d/"mock-count").write_text(str(count))',
            f'count+=1; (d/"mock-count").write_text(str(count)); Path({str(self.root / "uptime")!r}).write_text("424.0 0\\n")')
        capture.write_text(text)
        self.assertEqual(self.run_action('PROBE').returncode, 0)
        self.assertEqual(self.run_action('RUN').returncode, 0)
        self.assertEqual((self.d / 'mock-count').read_text(), '1')
        self.assertEqual((self.d / 'blink-stop').read_text(), 'reason=deadline\n')
        self.assertTrue((self.d / 'dds-during.raw').exists())
        self.assertEqual(self.run_action('RUN').returncode, 92)

    def test_pause_only_requests_cooperative_stop(self):
        self.assertEqual(self.run_action('PAUSE').returncode, 0)
        self.assertEqual((self.d / 'cancel').read_text(), 'cancel\n')
        self.assertFalse((self.root / 'calls').exists())
        self.assertEqual(self.run_action('PROBE').returncode, 94)

    def test_changed_pid_refused(self):
        (self.d / "native.pid").write_text("163\n")
        self.assertEqual(self.run_action("PROBE").returncode, 95)
        self.assertFalse((self.root / "calls").exists())

    def test_fresh_native_lifecycle_uses_once(self):
        (self.d / "native.mode").write_text("--once\n")
        (self.d / "native.timer").write_text("297\n")
        (self.root / "native-state").write_text("DDS_STATE attached timer=297 first=1 override=0 visible=0 others_idle=1\n")
        self.assertEqual(self.run_action("PROBE").returncode, 0)
        self.assertIn("--once 162 6015000\n", (self.root / "calls").read_text())

    def test_lifecycle_changes_after_install_refused(self):
        (self.root / "native-state").write_text("DDS_STATE attached timer=297 first=0 override=0 visible=0 others_idle=1\n")
        self.assertEqual(self.run_action("PROBE").returncode, 95)
        self.assertNotIn("--once", (self.root / "calls").read_text())

    def test_failed_inspection_never_draws_or_retries(self):
        (self.root / "fail").touch()
        self.assertEqual(self.run_action("PROBE").returncode, 96)
        self.assertEqual(self.run_action("PROBE").returncode, 92)
        self.assertNotIn("--once", (self.root / "calls").read_text())
        self.assertEqual((self.d / 'prewrite-abort').read_text(), 'no_display_started=1\n')

    def test_shooting_wake_rebinds_untouched_native_timer(self):
        self.prepare_layout_diagnosis()
        (self.d / 'diagnose-only').unlink()
        (self.d / 'shooting-overlay').write_text('1\n')
        (self.d / 'native.mode').write_text('--once-shooting-idle\n')
        (self.d / 'restore-proof').write_text('old proof\n')
        (self.root / 'native-state').write_text(
            'DDS_STATE attached timer=310 first=1 override=0 visible=0 others_idle=1\n'
            'DDS_FONT original_matches=1 bytes=128\n'
            'DDS_POSITION original_matches=1 x=30 y=250\n')
        self.assertEqual(self.run_action('PROBE').returncode, 0)
        self.assertIn('--once-shooting 162 6015000\n', (self.root / 'calls').read_text())
        self.assertEqual((self.d / 'native.timer').read_text(), '310\n')
        self.assertFalse((self.d / 'restore-proof').exists())
        self.assertFalse((self.d / 'prewrite-abort').exists())

    def test_shooting_rebind_refuses_unproven_state(self):
        self.prepare_layout_diagnosis()
        (self.d / 'diagnose-only').unlink()
        (self.d / 'shooting-overlay').write_text('1\n')
        (self.d / 'native.mode').write_text('--once-shooting-idle\n')
        valid = ('DDS_STATE attached timer=310 first=1 override=0 visible=0 others_idle=1\n'
                 'DDS_FONT original_matches=1 bytes=128\n'
                 'DDS_POSITION original_matches=1 x=30 y=250\n')
        for invalid in [valid.replace('first=1', 'first=0'), valid.replace('timer=310', 'timer=512'),
                        valid.replace('visible=0', 'visible=1'), valid.replace('original_matches=1', 'original_matches=0')]:
            (self.root / 'native-state').write_text(invalid)
            self.assertEqual(self.run_action('PROBE').returncode, 95)
            self.assertNotIn('--once', (self.root / 'calls').read_text())
            self.assertEqual((self.d / 'native.timer').read_text(), '239\n')
            self.assertEqual((self.d / 'prewrite-abort').read_text(), 'no_display_started=1\n')
            (self.d / 'claimed').rmdir()
            (self.d / 'prewrite-abort').unlink()

    def test_cancel_and_bad_command_never_claim(self):
        (self.d / "cancel").touch()
        self.assertEqual(self.run_action("PROBE").returncode, 94)
        self.assertEqual(self.run_action("HOLD").returncode, 64)
        self.assertFalse((self.d / "claimed").exists())

    def test_missing_mount_refuses_even_status(self):
        (self.root / "mounts").write_text("")
        self.assertEqual(self.run_action("STATUS").returncode, 90)
        self.assertEqual(self.run_action("PROBE").returncode, 90)
        self.assertFalse((self.d / "claimed").exists())

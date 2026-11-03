"""Real upload display shell + real management guards; fake native renderer.

No camera/network access. Exercise the cross-module lifetime and lock contract.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('transfer_tests', HERE.parent/'tests/test_display_transfer.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


class UploadDisplayTests(unittest.TestCase):
    setUpBase = fixture.ManagementTests.setUp
    tearDown = fixture.ManagementTests.tearDown
    runm = fixture.ManagementTests.runm

    def setUp(self):
        self.setUpBase()
        self.u = self.p/'uploader'; self.u.mkdir()
        self.owner = os.getpid(); self.token = f'{self.owner} 1234 1 240'
        (self.p/'mounts').write_text((self.p/'mounts').read_text()+f'a7c-upload-ram {self.u} tmpfs rw\n')
        (self.p/'proc'/str(self.owner)).mkdir()
        self.stat = self.p/'proc'/str(self.owner)/'stat'
        self.stat.write_text(f'{self.owner} (name with spaces) '+' '.join(['0']*19+['1234'])+'\n')
        (self.p/'uptime').write_text('10.00 0\n')
        (self.u/'display.active').write_text(self.token+'\n')
        (self.d/'shooting-overlay').write_text('1\n')
        (self.d/'manage.sh').write_text(self.script.read_text())
        self.mode='complete'; self.set_capture()
        source=(HERE/'worker.sh').read_text()
        for a,b in [('B=/bin/busybox',f'B={self.p}/bb'),('/setting/a7c-debug/ram/dds-once',str(self.d)),
                    ('/setting/a7c-uploader/ram',str(self.u)),('/proc/mounts',str(self.p/'mounts')),
                    ('/proc/sys/kernel/random/boot_id',str(self.p/'boot')),('/proc/uptime',str(self.p/'uptime')),
                    ('/proc/$owner/stat',str(self.p/'proc')+'/$owner/stat'),('/bin/ash','/bin/sh')]:
            source=source.replace(a,b)
        self.upload=self.p/'upload.sh'; self.upload.write_text(source)

    def set_capture(self):
        effect={
            'complete':f'rm -f "{self.u}/display.active"',
            'pause':f'touch "{self.u}/stop"',
            'lost-owner':f'echo invalid > "{self.stat}"',
            'new-owner':f'echo "{self.owner} 4321 2 240" > "{self.u}/display.active"',
            'deadline':f'echo "251.00 0" > "{self.p}/uptime"',
            'failure':'exit 91',
            'term':'kill -TERM "$PPID"',
        }[self.mode]
        capture=self.d/'capture'
        capture.write_text(f'''#!/bin/sh
if [ "$1" != --inspect ]; then
 case "$1" in --upload-shooting|--upload-shooting-idle) ;; *) exit 94;; esac
 echo draw >> "{self.p}/draws"
 {effect}
 echo 'DDS_CANCEL timer=381 transport=0 response=0'
 echo 'DDS_DONE display=0 cleanup=0 guardian=0 captures=0,0,0'
 echo restored >> "{self.p}/draws"
fi
echo 'DDS_STATE attached timer=381 first=0 override=0 visible=0 others_idle=1'
echo 'DDS_FONT original_matches=1 bytes=128'
echo 'DDS_POSITION original_matches=1 x=30 y=250'
'''); capture.chmod(0o700)

    def run_worker(self):
        return subprocess.run(['sh',str(self.upload),self.token],capture_output=True,text=True,timeout=5)

    def test_completion_pause_owner_loss_and_deadline_restore_once(self):
        for mode in ['complete','pause','lost-owner','new-owner','deadline','term']:
            with self.subTest(mode=mode):
                self.mode=mode; self.set_capture()
                (self.u/'display.active').write_text(self.token+'\n')
                (self.u/'stop').unlink(missing_ok=True)
                self.stat.write_text(f'{self.owner} (name) '+' '.join(['0']*19+['1234'])+'\n')
                (self.p/'uptime').write_text('10.00 0\n')
                (self.p/'draws').unlink(missing_ok=True)
                p=self.run_worker(); self.assertEqual(p.returncode,0,p.stderr)
                self.assertEqual((self.p/'draws').read_text(),'draw\nrestored\n')
                self.assertEqual((self.d/'status').read_text(),'stage=restored\n')
                self.assertEqual((self.d/'done').read_text(),'exit=0\n')
                self.assertFalse((self.d/'maintenance').exists())
                self.assertFalse((self.d/'blink-worker.running').exists())


    def test_optional_phase_timings_are_bounded_and_omit_request_identity(self):
        (self.u/'trace-timing').touch()
        result=self.run_worker(); self.assertEqual(result.returncode,0,result.stderr)
        rows=(self.d/'upload-timings.log').read_text().splitlines()
        self.assertEqual([line.split()[0] for line in rows],[
            'op=consumer_begin','op=native_binding_ready','op=rearm_begin',
            'op=rearm_end','op=renderer_exec','op=renderer_exit','op=consumer_end'])
        self.assertTrue(all(line.endswith('uptime=10.00') for line in rows))
        self.assertNotIn(self.token,'\n'.join(rows))


    def test_changed_native_post_frame_requires_fresh_clean_state(self):
        cap=(self.d/'capture').read_text()
        changed=cap.replace('captures=0,0,0','captures=0,0,98')
        # Only the upload render exits with pixel diagnostic 91; --inspect
        # remains the same mandatory untouched font/coordinate/state proof.
        changed=changed.replace(" echo restored", " echo 'DDS_LATE capture=0'\n exit 91\n echo restored",1)
        (self.d/'capture').write_text(changed)
        result=self.run_worker();self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('UPLOAD_DISPLAY_POST_FRAME_CHANGED',result.stdout)
        self.assertEqual((self.d/'status').read_text(),'stage=restored\n')
        # The next operation accepts the successful fresh inspection, not a
        # synthetic empty image, but still checks the exact current timer.
        self.assertEqual(self.runm('XLOCK').returncode,0)
        (self.d/'maintenance').rmdir()


    def test_post_frame_exception_still_rejects_modified_native_state(self):
        capture=self.d/'capture'
        changed=capture.read_text().replace('captures=0,0,0','captures=0,0,98')
        changed=changed.replace(' echo restored', " echo 'DDS_LATE capture=0'\n exit 91\n echo restored",1)
        changed=changed.replace('fi\necho', 'fi\nif [ -f \"'+str(self.p/'draws')+'\" ]; then echo \"DDS_FONT original_matches=0 bytes=128\"; exit 1; fi\necho')
        capture.write_text(changed)
        result=self.run_worker(); self.assertEqual(result.returncode,98,result.stdout+result.stderr)
        self.assertIn('UPLOAD_DISPLAY_POST_FRAME_CHANGED',result.stdout)
        self.assertEqual((self.d/'done').read_text(),'exit=98\n')
        self.assertNotEqual(self.runm('XLOCK').returncode,0)

    def test_post_frame_exception_does_not_accept_failed_cleanup(self):
        capture=self.d/'capture'
        changed=capture.read_text().replace('captures=0,0,0','captures=0,0,98').replace('cleanup=0','cleanup=1')
        changed=changed.replace(' echo restored', " echo 'DDS_LATE capture=0'\n exit 91\n echo restored",1)
        capture.write_text(changed)
        result=self.run_worker(); self.assertEqual(result.returncode,97,result.stdout+result.stderr)
        self.assertNotIn('UPLOAD_DISPLAY_POST_FRAME_CHANGED',result.stdout)
        self.assertEqual((self.d/'done').read_text(),'exit=97\n')

    def test_missing_request_or_reused_owner_does_not_draw(self):
        for contents in ['',f'{self.owner} 9999 1 240']:
            (self.u/'display.active').write_text(contents)
            self.assertEqual(self.run_worker().returncode,0)
            self.assertFalse((self.p/'draws').exists())
        (self.u/'display.active').write_text(self.token+'\n')
        self.stat.write_text(f'{self.owner} (name) '+' '.join(['0']*19+['9999'])+'\n')
        self.assertEqual(self.run_worker().returncode,0)
        self.assertFalse((self.p/'draws').exists())

    def test_failed_native_cleanup_blocks_next_display(self):
        self.mode='failure'; self.set_capture()
        self.assertEqual(self.run_worker().returncode,97)
        self.assertEqual((self.d/'done').read_text(),'exit=97\n')
        self.mode='complete'; self.set_capture()
        self.assertEqual(self.run_worker().returncode,95)
        self.assertEqual((self.p/'draws').read_text(),'draw\n')

    def test_update_lock_is_not_stolen_and_cancel_not_cleared(self):
        (self.d/'maintenance').mkdir()
        self.assertEqual(self.run_worker().returncode,92)
        self.assertTrue((self.d/'maintenance').is_dir())
        self.assertFalse((self.p/'draws').exists())
        (self.d/'maintenance').rmdir(); (self.d/'cancel').touch()
        self.assertEqual(self.run_worker().returncode,0)
        self.assertTrue((self.d/'cancel').exists())
        self.assertFalse((self.p/'draws').exists())

    def test_deferred_native_binding_is_optional_and_retried_on_next_upload(self):
        prepare=self.d/'prepare.sh'
        prepare.write_text('#!/bin/sh\nexit 75\n');prepare.chmod(0o700)
        result=self.run_worker();self.assertEqual(result.returncode,0)
        self.assertIn('UPLOAD_DISPLAY_NOT_READY',result.stdout)
        self.assertFalse((self.p/'draws').exists())
        self.assertFalse((self.d/'maintenance').exists())
        prepare.write_text('#!/bin/sh\nexit 0\n')
        self.assertEqual(self.run_worker().returncode,0)
        self.assertEqual((self.p/'draws').read_text(),'draw\nrestored\n')


if __name__=='__main__': unittest.main()

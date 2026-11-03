from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class NativeUploadTrialTests(unittest.TestCase):
    def test_one_request_restore_and_failed_cleanup_lock(self):
        for failed in (False,True):
            with self.subTest(failed=failed),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);d=p/'display';u=p/'upload';n=d/'native-rect-v18'
                n.mkdir(parents=True);u.mkdir()
                shim=p/'busybox';shim.write_text('#!/bin/sh\ncase "$1" in pidof) echo 42;; sha256sum) shift; shasum -a 256 "$@";; *) exec "$@";; esac\n');shim.chmod(0o700)
                (p/'boot').write_text('boot-a\n');(n/'boot-id').write_text('boot-a\n');(n/'im.pid').write_text('42\n')
                original=(ROOT/'upload/worker.sh').read_bytes();(n/'consumer.original').write_bytes(original)
                token='123 456 1 240';(u/'display.active').write_text(token+'\n')
                script=(ROOT/'module/upload_trial.sh').read_text().replace('B=/bin/busybox',f'B={shim}').replace('D=/setting/a7c-debug/ram/dds-once',f'D={d}').replace('U=/setting/a7c-uploader/ram',f'U={u}').replace('/proc/sys/kernel/random/boot_id',str(p/'boot'))
                consumer=u/'upload-display.sh';consumer.write_text(script)
                probe=n/'probe';probe.write_text('#!/bin/sh\n'+('echo failed; exit 77\n' if failed else 'echo "MODULE_DONE install=0 load=0 restore=0 unload=0 marker=0 guardian=0 remaining=0"\n'))
                probe.chmod(0o700);sampler=n/'sampler';sampler.write_text('#!/bin/sh\nexit 0\n');sampler.chmod(0o700)
                result=subprocess.run(['sh',str(consumer),token],capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,77 if failed else 0,result.stdout+result.stderr)
                self.assertEqual(consumer.read_bytes(),original)
                self.assertEqual((d/'maintenance').exists(),failed)
                self.assertEqual((n/'trial.rc').read_text().strip(),'77' if failed else '0')

class NativeServiceConsumerTests(unittest.TestCase):
    def test_reusable_requests_and_failed_cleanup_lock(self):
        for failed in (False,True):
            with self.subTest(failed=failed),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);d=p/'display';u=p/'upload';n=d/'native-service'
                n.mkdir(parents=True);u.mkdir()
                shim=p/'busybox';shim.write_text('#!/bin/sh\ncase "$1" in pidof) echo 42;; *) exec "$@";; esac\n');shim.chmod(0o700)
                (p/'boot').write_text('boot-a\n');(n/'boot-id').write_text('boot-a\n');(n/'im.pid').write_text('42\n')
                script=(ROOT/'upload/native-consumer.sh').read_text().replace('B=/bin/busybox',f'B={shim}').replace('D=/setting/a7c-debug/ram/dds-once',f'D={d}').replace('U=/setting/a7c-uploader/ram',f'U={u}').replace('/proc/sys/kernel/random/boot_id',str(p/'boot'))
                consumer=u/'upload-display.sh';consumer.write_text(script)
                probe=n/'probe';probe.write_text('#!/bin/sh\n'+('echo failed; exit 77\n' if failed else 'echo "SERVICE_UPLOAD_DONE progress=0 guardian=0 capture=0 idle=1"\n'))
                probe.chmod(0o700)
                for serial in range(1,2 if failed else 3):
                    token=f'123 456 {serial} 240';(u/'display.active').write_text(token+'\n')
                    for frame in ('before','during','after'):(n/(frame+'.raw')).write_bytes(b'old')
                    result=subprocess.run(['sh',str(consumer),token],capture_output=True,text=True,timeout=5)
                    self.assertEqual(result.returncode,77 if failed else 0,result.stdout+result.stderr)
                    self.assertEqual(consumer.read_text(),script)
                    self.assertEqual((d/'maintenance').exists(),failed)
                    self.assertEqual((n/'during.raw').read_bytes(),b'old')
                bad=subprocess.run(['sh',str(consumer),'stale-token'],capture_output=True,text=True,timeout=5)
                self.assertEqual(bad.returncode,86)

if __name__=='__main__':unittest.main()

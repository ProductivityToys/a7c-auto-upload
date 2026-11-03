"""Exercise boot staging/native binding with fake mounts and read-only /proc.

Runs the real shell scripts; never contacts a camera or mounts a filesystem.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.p = self.root/'persistent'
        self.g = self.root/'debug'
        self.d = self.g/'dds-once'
        self.u = self.root/'upload'
        self.proc = self.root/'proc'
        for p in (self.p, self.g, self.u, self.proc/'sys/kernel/random', self.proc/'42'):
            p.mkdir(parents=True, mode=0o700)
        self.mounts = self.proc/'mounts'
        self.mounts.write_text(f'a7c-upload-ram {self.u} tmpfs rw\na7c-debug-ram {self.g} tmpfs rw\n')
        (self.proc/'sys/kernel/random/boot_id').write_text('test-boot\n')
        self.bb = self.root/'bb'
        self.bb.write_text(f'''#!/bin/sh
case "$1" in
 sha256sum) shift; exec shasum -a 256 "$@";;
 pidof) echo 42;;
 sleep) :;;
 mount) echo "$7 $8 tmpfs rw" >> '{self.mounts}';;
 *) exec "$@";;
esac
''')
        self.bb.chmod(0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def transform(self, text):
        pairs = [('B=/bin/busybox', 'B='+str(self.bb)),
                 ('/setting/a7c-debug/ram/dds-once', str(self.d)),
                 ('/setting/a7c-debug/ram', str(self.g)),
                 ('/setting/a7c-uploader/ram', str(self.u)),
                 ('/setting/a7c-display', str(self.p)),
                 ('/proc/', str(self.proc)+'/'), ('/bin/ash', '/bin/sh'),
                 ('[ "$uid" = 0 ]', f'[ "$uid" = {os.getuid()} ]'),
                 ('[ "$gid" = 0 ]', f'[ "$gid" = {os.getgid()} ]'),
                 (' [ "$mode" = "$2" ]', ' mode=${mode%@}; [ "$mode" = "$2" ]')]
        for a,b in pairs: text=text.replace(a,b)
        return text

    def run_script(self, name):
        script=self.root/(name+'.runner')
        script.write_text(self.transform((HERE/name).read_text()))
        return subprocess.run(['sh', str(script)], capture_output=True, text=True, timeout=6)


class StageTests(Fixture):
    names = 'capture redraw listener launch blink-launch ui-layout collector.sh action.sh manage.sh blink-worker.sh prepare.sh consumer.sh native-start.sh native-probe native-module.so native.sha256'.split()
    def setUp(self):
        super().setUp()
        self.native_paths = ['/usr/lib/libObj.so','/usr/lib/libosal_uipc.so','/usr/kmod/utimer.ko','/lib/libc-2.11.2.so','/lib/librt-2.11.2.so','/usr/bin/testcmd.elf','/usr/lib/libtestcmd.so','/usr/bin/im.elf','/usr/lib/libIMDB.so']
        self.native_manifest=''
        for i, path in enumerate(self.native_paths):
            dest=self.root/'native'/path[1:];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(f'native{i}')
            self.native_manifest+=hashlib.sha256(dest.read_bytes()).hexdigest()+' '+str(dest)+'\n'
        for name in self.names:
            self.write(name,'#!/bin/sh\nexit 0\n')
        self.write('native.sha256',self.native_manifest)
        self.write('prepare.sh','#!/bin/sh\nexit 75\n')
        self.write('enabled','a7c-upload-display-v1\n')
        self.manifest()

    def transform(self, text):
        text=super().transform(text)
        for path in self.native_paths: text=text.replace(path,str(self.root/'native'/path[1:]))
        return text

    def write(self,name,text):
        p=self.p/name;p.write_text(text);p.chmod(0o600)

    def manifest(self):
        self.write('manifest',''.join(hashlib.sha256((self.p/n).read_bytes()).hexdigest()+' '+n+'\n' for n in self.names))

    def test_stage_deferred_native_still_publishes_ram_consumer(self):
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.p.iterdir()}
        r=self.run_script('stage.sh');self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        self.assertIn('DISPLAY_PREPARE rc=75',r.stdout)
        self.assertEqual((self.d/'enabled').read_text(),'1\n')
        self.assertEqual((self.u/'upload-display.sh').read_bytes(),(self.p/'consumer.sh').read_bytes())
        self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.p.iterdir()})
        self.assertFalse((self.g/'display-stage.lock').exists())

    def test_repeat_keeps_wireless_update_and_cleanup_proof(self):
        self.assertEqual(self.run_script('stage.sh').returncode,0)
        (self.d/'capture').write_text('accepted wireless update')
        (self.d/'overlay.log').write_text('DDS_CANCEL proof')
        self.assertEqual(self.run_script('stage.sh').returncode,0)
        self.assertEqual((self.d/'capture').read_text(),'accepted wireless update')
        self.assertEqual((self.d/'overlay.log').read_text(),'DDS_CANCEL proof')

    def test_bad_hash_or_permissions_prevents_publication(self):
        (self.p/'capture').write_text('changed')
        self.assertEqual(self.run_script('stage.sh').returncode,90)
        self.assertFalse(self.d.exists());self.assertFalse((self.u/'upload-display.sh').exists())
        self.manifest();(self.p/'capture').chmod(0o644)
        self.assertEqual(self.run_script('stage.sh').returncode,90)

    def test_native_mismatch_prevents_publication(self):
        (self.root/'native/usr/lib/libObj.so').write_text('different firmware')
        self.assertEqual(self.run_script('stage.sh').returncode,90)
        self.assertFalse(self.d.exists())

    def test_duplicate_manifest_and_symlink_rejected(self):
        self.write('manifest',(self.p/'manifest').read_text()+(self.p/'manifest').read_text().splitlines()[0]+'\n')
        self.assertEqual(self.run_script('stage.sh').returncode,90)
        self.manifest();(self.p/'capture').unlink();(self.p/'capture').symlink_to(self.p/'redraw')
        self.assertEqual(self.run_script('stage.sh').returncode,90)

    def test_no_parent_mount_never_creates_a_competing_mount(self):
        self.mounts.write_text(f'a7c-upload-ram {self.u} tmpfs rw\n')
        r=self.run_script('stage.sh');self.assertEqual(r.returncode,90)
        self.assertIn('parent_not_ready',r.stdout);self.assertFalse(self.d.exists())
        self.assertNotIn('a7c-debug-ram',self.mounts.read_text())

    def test_foreign_mount_and_partial_runtime_are_preserved(self):
        self.d.mkdir();(self.d/'unknown').write_text('preserve')
        self.mounts.write_text(self.mounts.read_text()+f'foreign {self.d} tmpfs rw\n')
        r=self.run_script('stage.sh');self.assertEqual(r.returncode,90);self.assertIn('foreign_runtime',r.stdout)
        self.mounts.write_text(self.mounts.read_text().replace('foreign ','a7c-display-ram '))
        r=self.run_script('stage.sh');self.assertEqual(r.returncode,90);self.assertIn('partial_runtime',r.stdout)
        self.assertEqual((self.d/'unknown').read_text(),'preserve')

    def test_changed_bundle_old_boot_or_upload_active_rejected(self):
        self.assertEqual(self.run_script('stage.sh').returncode,0)
        (self.d/'boot-id').write_text('other boot')
        self.assertEqual(self.run_script('stage.sh').returncode,90)
        (self.d/'boot-id').write_text('test-boot\n')
        self.write('capture','new');self.manifest()
        self.assertEqual(self.run_script('stage.sh').returncode,90)
        (self.u/'display.active').touch()
        r=self.run_script('stage.sh');self.assertEqual(r.returncode,90);self.assertIn('REJECTED active',r.stdout)


class PrepareTests(Fixture):
    def setUp(self):
        super().setUp();self.d.mkdir()
        self.mounts.write_text(self.mounts.read_text()+f'a7c-display-ram {self.d} tmpfs rw\n')
        (self.d/'boot-id').write_text('test-boot\n')
        (self.proc/'42/exe').symlink_to('/usr/bin/im.elf')
        self.set_start('1234')
        (self.d/'enabled').write_text('1\n')
        (self.proc/'42/maps').write_text('06015000-06315000 r-xp 00000000 fc:0f 123 /usr/lib/libObj.so\n')
        (self.proc/str(os.getpid())).mkdir()
        (self.proc/str(os.getpid())/'exe').symlink_to(self.d/'listener')
        self.set_inspect()
        for name in ('collector.sh','launch'):
            p=self.d/name;p.write_text('#!/bin/sh\nexit 0\n');p.chmod(0o700)
        self.launch='#!/bin/sh\necho launch >> "'+str(self.root/'launches')+'"\nmkdir "'+str(self.d/'running')+'"\necho '+str(os.getpid())+' > "'+str(self.d/'listener.pid')+'"\n'
        (self.d/'launch').write_text(self.launch)

    def set_start(self, start):
        (self.proc/'42/stat').write_text('42 (native name) '+' '.join(['0']*19+[start])+'\n')

    def set_inspect(self,first=1,font=1):
        p=self.d/'capture';p.write_text(f'''#!/bin/sh
echo 'DDS_STATE attached timer=381 first={first} override=0 visible=0 others_idle=1'
echo 'DDS_FONT original_matches={font} bytes=128'
echo 'DDS_POSITION original_matches=1 x=30 y=250'
''');p.chmod(0o700)

    def test_binds_unique_native_and_starts_listener_only_once(self):
        r=self.run_script('prepare.sh');self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        self.assertEqual((self.d/'native.base').read_text(),'06015000\n')
        self.assertEqual((self.d/'native.start').read_text(),'1234\n')
        self.assertEqual(self.run_script('prepare.sh').returncode,0)
        self.assertEqual((self.root/'launches').read_text(),'launch\n')

    def test_reused_pid_or_other_boot_cannot_reuse_ready(self):
        self.assertEqual(self.run_script('prepare.sh').returncode,0)
        self.set_start('9999');self.assertEqual(self.run_script('prepare.sh').returncode,75)
        self.set_start('1234');(self.d/'boot-id').write_text('old')
        self.assertEqual(self.run_script('prepare.sh').returncode,75)

    def test_unknown_first_zero_modified_font_and_ambiguous_mapping_do_not_launch(self):
        self.set_inspect(first=0);self.assertEqual(self.run_script('prepare.sh').returncode,75)
        self.set_inspect(font=0);self.assertEqual(self.run_script('prepare.sh').returncode,75)
        self.set_inspect();p=self.proc/'42/maps';p.write_text(p.read_text()*2)
        self.assertEqual(self.run_script('prepare.sh').returncode,75)
        self.assertFalse((self.root/'launches').exists())

    def test_busy_or_claimed_is_never_reclaimed(self):
        for name in ('maintenance','claimed','init.lock'):
            (self.d/name).mkdir();self.assertEqual(self.run_script('prepare.sh').returncode,75)
            self.assertTrue((self.d/name).exists());(self.d/name).rmdir()
        self.assertFalse((self.root/'launches').exists())

    def test_slow_listener_is_adopted_without_second_launch(self):
        (self.d/'launch').write_text('#!/bin/sh\necho launch >> "'+str(self.root/'launches')+'"\n')
        self.assertEqual(self.run_script('prepare.sh').returncode,75)
        (self.d/'listener.pid').write_text(str(os.getpid())+'\n')
        self.assertEqual(self.run_script('prepare.sh').returncode,0)
        self.assertEqual((self.root/'launches').read_text(),'launch\n')


if __name__ == '__main__': unittest.main()

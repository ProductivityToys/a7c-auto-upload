"""Real authenticated sockets and real management shell, no camera access."""
import hashlib
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

D = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared', D.parent/'debugger/tests/test_listener.py')
shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
sys.path.insert(0, str(D))
from transfer_client import request


class TransferSocketTests(unittest.TestCase):
    additional_flags = ['-DDISPLAY_OBSERVER_ONLY', '-DDISPLAY_BLINK_CONTROL', '-DDISPLAY_TRANSFER_PROTOCOL']
    setUpBase = shared.ListenerTests.setUp
    tearDown = shared.ListenerTests.tearDown
    call = shared.ListenerTests.call

    def setUp(self):
        self.setUpBase()
        (self.p/'manage.sh').write_text('#!/bin/sh\necho "$1 $2" >> "'+str(self.p/'manage-calls')+'"\n')

    def req(self, verb, arg='', payload=None):
        return request(verb, arg, payload, host='127.0.0.1', port=self.port, token_file=self.t)

    def test_frame_exact_stream_and_client_digest(self):
        data = bytes(range(256))*2400
        (self.r/'dds-during.raw').write_bytes(data)
        r = self.req('FRAME', 'during')
        self.assertEqual(r['data'], data)
        self.assertEqual(r['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(r['rc'], 0)
        self.assertIn('XREADLOCK', (self.p/'manage-calls').read_text())
        (self.r/'dds-during.raw').write_bytes(data[:-1])
        self.assertEqual(self.req('FRAME', 'during')['rc'], 96)

    def test_push_and_frame_namespace_rejections(self):
        for verb, arg in [('FRAME', '../token'), ('PUSH', 'listener:1:'+'a'*64),
                          ('PUSH', 'capture:65537:'+'a'*64), ('PUSH', 'capture:01:'+'a'*64),
                          ('SCREEN', 'extra'), ('UPLOAD_ENABLE', 'extra'), ('ROLLBACK', 'manage'), ('XLOCK', ''), ('XREADLOCK', '')]:
            self.assertEqual(self.call(verb, extra=' '+arg if arg else ''), 'REJECTED\n')
        r = self.req('PUSH', 'action', b'candidate')
        self.assertEqual(r['rc'], 0)
        calls = (self.p/'manage-calls').read_text()
        self.assertIn('XCOMMIT action:9:'+hashlib.sha256(b'candidate').hexdigest(), calls)
        self.assertFalse((self.r/'incoming').exists())
        self.assertEqual(self.req('PUSH', 'capture', b'not an ELF')['rc'], 96)
        self.assertEqual(self.req('UPLOAD_ENABLE')['rc'],0)
        self.assertIn('XENABLE', (self.p/'manage-calls').read_text())

    def raw_push(self, declared, actual, digest):
        with socket.create_connection(('127.0.0.1', self.port), timeout=3) as s, s.makefile('rb') as f:
            hello = f.readline().decode().split(); seq = int(hello[2])+1
            s.sendall(('AUTH %s %s %d PUSH capture:%d:%s\n' % ('a'*64, hello[1], seq, declared, digest)).encode())
            self.assertEqual(f.readline().decode(), 'READY %d %d\n' % (seq, declared))
            s.sendall(actual);s.shutdown(socket.SHUT_WR)
            return f.read().decode()

    def test_corrupt_and_truncated_upload_never_commit(self):
        for size, data in [(9, b'truncated'), (10, b'partial')]:
            self.assertIn('PUSH 98', self.raw_push(size, data, 'b'*64))
            self.assertFalse((self.r/'incoming').exists())
        self.assertNotIn('XCOMMIT', (self.p/'manage-calls').read_text())
        self.assertIn('STATUS 0', self.call('STATUS'))

    test_auth_session_replay_and_unknown_action = shared.ListenerTests.test_auth_session_replay_and_unknown_action
    test_idle_blocks_without_periodic_timer_and_term_exits = shared.ListenerTests.test_idle_blocks_without_periodic_timer_and_term_exits


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);self.d=self.p/'ram';self.d.mkdir()
        (self.p/'mounts').write_text('a7c-display-ram '+str(self.d)+' tmpfs rw\n')
        (self.p/'boot').write_text('boot\n')
        (self.p/'proc').mkdir()
        bb=self.p/'bb';bb.write_text('#!/bin/sh\nif [ "$1" = pidof ]; then echo 162; elif [ "$1" = sha256sum ]; then shift; shasum -a 256 "$@"; else exec "$@"; fi\n');bb.chmod(0o700)
        src=(D/'dds_wireless_manage.sh').read_text()
        for a,b in [('B=/bin/busybox','B='+str(bb)),('/setting/a7c-debug/ram/dds-once',str(self.d)),('/proc/mounts',str(self.p/'mounts')),('/proc/sys/kernel/random/boot_id',str(self.p/'boot')),('/proc/[0-9]*/exe',str(self.p/'proc/[0-9]*/exe')),('/bin/ash','/bin/sh')]:src=src.replace(a,b)
        # Batch procfs scan requires the caller's own resolvable link. Each
        # real management shell gets one in this isolated synthetic procfs.
        src=src.replace('/proc/$$/exe',str(self.p/'proc')+'/$$/exe')
        setup='mkdir -p "'+str(self.p/'proc')+'/$$"\nln -sf /bin/sh "'+str(self.p/'proc')+'/$$/exe"\n'
        src=src.replace('\ncase "$1" in\n','\n'+setup+'case "$1" in\n',1)
        self.script=self.p/'manage.sh';self.script.write_text(src)
        for n,v in [('boot-id','boot'),('native.pid','162'),('native.base','6015000'),('native.timer','381'),('done','exit=0'),('status','stage=restored'),('overlay.log','DDS_CANCEL timer=381 transport=0 response=0\nDDS_DONE display=0 cleanup=0 guardian=0 captures=0,0,0')]: (self.d/n).write_text(v+'\n')
        cap=self.d/'capture';cap.write_text('#!/bin/sh\necho "DDS_STATE attached timer=381 first=0 override=0 visible=0 others_idle=1"\necho "DDS_FONT original_matches=1 bytes=128"\necho "DDS_POSITION original_matches=1 x=30 y=250"\n');cap.chmod(0o700)
        (self.d/'action.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.d/'claimed').mkdir();(self.d/'blink-worker.started').mkdir()

    def tearDown(self):self.tmp.cleanup()
    def runm(self,verb,arg=''):
        return subprocess.run(['sh',str(self.script),verb,arg],capture_output=True,text=True,timeout=4)
    def test_busy_or_failed_transaction_refuses_update(self):
        (self.d/'blink-worker.running').mkdir()
        self.assertEqual(self.runm('XLOCK').returncode,92)
        (self.d/'blink-worker.running').rmdir();(self.d/'done').write_text('exit=97\n')
        self.assertEqual(self.runm('XLOCK').returncode,92)
    def test_successful_rearm_preserves_cancel_proof(self):
        self.assertEqual(self.runm('XLOCK').returncode,0)
        self.assertEqual(self.runm('XREARM').returncode,0)
        self.assertFalse((self.d/'claimed').exists())
        self.assertEqual((self.d/'native.mode').read_text(),'--once-shooting-idle\n')
        self.assertEqual(self.runm('XIDLE').returncode,0)
        (self.p/'boot').write_text('other\n')
        self.assertNotEqual(self.runm('XIDLE').returncode,0)
    def test_existing_maintenance_lock_is_never_stolen(self):
        (self.d/'maintenance').mkdir()
        self.assertEqual(self.runm('XLOCK').returncode,92)
        self.assertTrue((self.d/'maintenance').is_dir())
    def test_fresh_native_timer_rebinds_only_untouched_lifecycle(self):
        original=(self.d/'capture').read_text()
        (self.d/'capture').write_text(original.replace('timer=381 first=0','timer=482 first=0'))
        self.assertEqual(self.runm('XLOCK').returncode,0)
        self.assertNotEqual(self.runm('XREARM').returncode,0)
        self.assertEqual((self.d/'native.timer').read_text(),'381\n')
        (self.d/'capture').write_text(original.replace('timer=381 first=0','timer=482 first=1'))
        (self.d/'restore-proof').write_text('boot 162 381\n')
        self.assertEqual(self.runm('XREARM').returncode,0)
        self.assertEqual((self.d/'native.timer').read_text(),'482\n')
        self.assertEqual((self.d/'native.mode').read_text(),'--once-shooting\n')
        self.assertFalse((self.d/'restore-proof').exists())
    def test_failed_frame_read_is_allowed_but_mutations_remain_blocked(self):
        (self.d/'done').write_text('exit=97\n')
        self.assertEqual(self.runm('XREADLOCK').returncode,0)
        self.assertNotEqual(self.runm('XREARM').returncode,0)
        self.assertEqual(self.runm('XUNLOCK').returncode,0)
        self.assertEqual(self.runm('XLOCK').returncode,92)
        (self.d/'blink-worker.running').mkdir()
        self.assertEqual(self.runm('XREADLOCK').returncode,92)
        (self.d/'blink-worker.running').rmdir()
        guard=self.p/'proc/999';guard.mkdir();(guard/'exe').symlink_to(self.d/'capture')
        self.assertEqual(self.runm('XREADLOCK').returncode,92)
    def test_frame_read_refuses_claimed_but_not_started_worker(self):
        (self.d/'done').unlink()
        self.assertEqual(self.runm('XREADLOCK').returncode,92)
        self.assertFalse((self.d/'maintenance').exists())
    def test_prewrite_abort_rearms_only_with_required_lifecycle_proof(self):
        (self.d/'done').write_text('exit=97\n')
        (self.d/'status').write_text('stage=upload-display-failed rc=97\n')
        (self.d/'overlay.log').write_text('DDS_GUARD ready=1\nDDS_ABORT baseline_capture=98 guardian=0\n')
        self.assertEqual(self.runm('XLOCK').returncode,0)
        self.assertNotEqual(self.runm('XREARM').returncode,0)  # first=0, no old proof
        (self.d/'restore-proof').write_text('boot 162 381\n')
        self.assertEqual(self.runm('XREARM').returncode,0)
        self.assertEqual((self.d/'native.mode').read_text(),'--once-shooting-idle\n')
    def test_abort_log_with_native_write_is_not_recoverable(self):
        (self.d/'done').write_text('exit=97\n')
        for line in ['DDS_SEND command=259','DDS_FONT install=0','DDS_ARM timer=381']:
            (self.d/'overlay.log').write_text('DDS_GUARD ready=1\n'+line+'\nDDS_ABORT baseline_capture=98 guardian=0\n')
            self.assertEqual(self.runm('XLOCK').returncode,92)
    def test_fresh_prewrite_abort_needs_no_cancel_proof(self):
        cap=self.d/'capture';cap.write_text(cap.read_text().replace('first=0','first=1'))
        (self.d/'done').write_text('exit=97\n')
        (self.d/'status').write_text('stage=upload-display-failed rc=97\n')
        (self.d/'overlay.log').write_text('DDS_GUARD ready=1\nDDS_ABORT baseline_capture=98 guardian=0\n')
        self.assertEqual(self.runm('XLOCK').returncode,0)
        self.assertEqual(self.runm('XREARM').returncode,0)
        self.assertEqual((self.d/'native.mode').read_text(),'--once-shooting\n')
    def test_explicit_preflight_abort_requires_no_overlay_and_fresh_idle(self):
        (self.d/'done').write_text('exit=95\n')
        (self.d/'status').write_text('stage=layout-diagnosis\n')
        (self.d/'overlay.log').unlink()
        self.assertEqual(self.runm('XLOCK').returncode,92)  # no proof
        (self.d/'prewrite-abort').write_text('no_display_started=1\n')
        (self.d/'overlay.log').write_text('DDS_FONT install=0\n')
        self.assertEqual(self.runm('XLOCK').returncode,92)
        (self.d/'overlay.log').unlink()
        self.assertEqual(self.runm('XLOCK').returncode,0)
        self.assertNotEqual(self.runm('XREARM').returncode,0)  # first=0 without proof
        cap=self.d/'capture';cap.write_text(cap.read_text().replace('timer=381 first=0','timer=310 first=1'))
        self.assertEqual(self.runm('XREARM').returncode,0)
        self.assertEqual((self.d/'native.timer').read_text(),'310\n')
        self.assertFalse((self.d/'prewrite-abort').exists())
    def test_explicit_enable_refuses_active_upload_and_failed_native_state(self):
        u=self.p/'upload';u.mkdir();(u/'display.disabled').touch()
        s=self.script.read_text().replace('/setting/a7c-uploader/ram',str(u));self.script.write_text(s)
        (self.p/'mounts').write_text((self.p/'mounts').read_text()+f'a7c-upload-ram {u} tmpfs rw\n')
        self.assertEqual(self.runm('XLOCK').returncode,0)
        (u/'display.active').touch();self.assertEqual(self.runm('XENABLE').returncode,92)
        self.assertTrue((u/'display.disabled').exists());(u/'display.active').unlink()
        (self.d/'done').write_text('exit=97\n');self.assertEqual(self.runm('XENABLE').returncode,95)
        self.assertTrue((u/'display.disabled').exists());(self.d/'done').write_text('exit=0\n')
        self.assertEqual(self.runm('XENABLE').returncode,0);self.assertFalse((u/'display.disabled').exists())
    def test_atomic_script_commit_and_rollback(self):
        self.assertEqual(self.runm('XLOCK').returncode,0)
        original=(self.d/'action.sh').read_bytes();new=b'#!/bin/sh\nexit 7\n'
        (self.d/'incoming').write_bytes(new)
        spec='action:%d:%s'%(len(new),hashlib.sha256(new).hexdigest())
        self.assertEqual(self.runm('XCOMMIT',spec).returncode,0)
        self.assertEqual((self.d/'action.sh').read_bytes(),new)
        self.assertEqual(self.runm('XROLLBACK','action').returncode,0)
        self.assertEqual((self.d/'action.sh').read_bytes(),original)
    def test_digest_syntax_and_elf_refusal_preserve_active(self):
        self.assertEqual(self.runm('XLOCK').returncode,0)
        original=(self.d/'action.sh').read_bytes()
        for data,role,digest in [(b'bad','action','a'*64),(b'if then','action',None),(b'not ELF','capture',None)]:
            (self.d/'incoming').write_bytes(data)
            spec='%s:%d:%s'%(role,len(data),digest or hashlib.sha256(data).hexdigest())
            self.assertNotEqual(self.runm('XCOMMIT',spec).returncode,0)
            self.assertEqual((self.d/'action.sh').read_bytes(),original)

if __name__=='__main__':unittest.main()

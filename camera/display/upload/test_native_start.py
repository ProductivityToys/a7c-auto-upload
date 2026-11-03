from pathlib import Path
import subprocess,tempfile,unittest
HERE=Path(__file__).resolve().parent
class NativeStartTests(unittest.TestCase):
 def test_binding_restart_and_immutable_module(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);d=r/'display';u=r/'upload';b=r/'bt';proc=r/'proc';d.mkdir();u.mkdir();b.mkdir();(proc/'sys/kernel/random').mkdir(parents=True);(proc/'42').mkdir()
   (proc/'sys/kernel/random/boot_id').write_text('boot\n');(proc/'42/maps').write_text('')
   (proc/'mounts').write_text(f'a7c-display-ram {d} tmpfs rw\nnone {b} tmpfs rw\n')
   (d/'native-module.so').write_bytes(b'module-v1');(u/'worker.pid').write_text('77\n')
   (d/'native-probe').write_text('#!/bin/sh\nif [ "$1" = --inspect-marker ]; then [ -f "'+str(r/'retired')+'" ]; exit $?; fi\n[ "$1" != --service-on ] || echo bind >> "'+str(r/'calls')+'"\nexit 0\n')
   bb=r/'bb';bb.write_text('#!/bin/sh\ncase "$1" in pidof) echo 42;; sha256sum) shift; exec shasum -a 256 "$@";; sleep) :;; *) exec "$@";; esac\n');bb.chmod(0o700)
   script=HERE.joinpath('native-start.sh').read_text().replace('B=/bin/busybox',f'B={bb}').replace('/setting/a7c-debug/ram/dds-once',str(d)).replace('/setting/a7c-uploader/ram',str(u)).replace('/tmp_bt',str(b)).replace('/proc/',str(proc)+'/')
   runner=r/'run';runner.write_text(script)
   def run():return subprocess.run(['sh',str(runner)],capture_output=True,text=True,timeout=5)
   first=run();self.assertEqual(first.returncode,0,first.stdout+first.stderr);self.assertEqual((d/'native-service/owner').read_text(),'77\n')
   (u/'worker.pid').write_text('88\n');second=run();self.assertEqual(second.returncode,0,second.stdout+second.stderr);self.assertEqual((d/'native-service/owner').read_text(),'88\n');self.assertEqual((r/'calls').read_text(),'bind\nbind\n')
   (r/'retired').touch();retired=run();self.assertEqual(retired.returncode,78);self.assertIn('NATIVE_SERVICE_RETIRED',retired.stdout);self.assertEqual((r/'calls').read_text(),'bind\nbind\n');(r/'retired').unlink()
   (d/'native-module.so').write_bytes(b'changed');self.assertEqual(run().returncode,94);self.assertEqual((b/'a70.so').read_bytes(),b'module-v1')
   (d/'native-module.so').write_bytes(b'module-v1');(u/'display.active').write_text('active');self.assertEqual(run().returncode,92)
if __name__=='__main__':unittest.main()

"""Boot boundary: verified private config/payloads, tmpfs-only runtime, stdin secret."""
import hashlib,os,pathlib,subprocess,tempfile,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class BootTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.tmp.name);self.d=self.p/'ram';self.d.mkdir();self.c=self.p/'plainftp';self.c.mkdir(mode=0o700)
  self.mounts=self.p/'mounts';self.mounts.write_text('a7c-upload-ram '+str(self.d)+' tmpfs rw 0 0\n')
  self.bb=self.p/'bb';self.bb.write_text('#!/bin/sh\ncase "$1" in sha256sum) shift; exec shasum -a 256 "$@";; *) exec "$@";; esac\n');self.bb.chmod(0o700)
  config='a7c-plainftp-v1\n127.0.0.1\n21\nuploader\n/upload with spaces\n'
  self.write('config',config);self.write('password','test-password-never-log\n')
  files={n:'fixture' for n in ['monitor','relay','lease','local-media','sd-monitor','discovery','plain-runtime.sh']}
  files['plainftp']='#!/bin/sh\n[ "$1" = namespace ] && [ "$2" = 127.0.0.1 ]\n'
  files['plain-worker.sh']='#!/bin/sh\nIFS= read -r secret\n[ "$secret" = test-password-never-log ] || exit 91\n[ "$4" = "/upload with spaces" ] || exit 92\n[ -z "$FTP_PASSWORD" ] || exit 93\necho started\nexit 42\n'
  self.files=files
  for n,data in files.items():self.write(n,data)
  self.write('manifest',''.join(hashlib.sha256(v.encode()).hexdigest()+' '+n+'\n' for n,v in files.items()))
  s=(SRC/'boot.sh').read_text().replace('B=/bin/busybox','B='+str(self.bb)).replace('/setting/a7c-uploader',str(self.p)).replace('/setting/a7c-display',str(self.p/'display')).replace('/proc/mounts',str(self.mounts)).replace('/bin/ash','/bin/sh').replace(' [ "$mode" = "$2" ]', ' mode=${mode%@}; [ "$mode" = "$2" ]').replace('[ "$uid" = 0 ]','[ "$uid" = '+str(os.getuid())+' ]').replace('[ "$gid" = 0 ]','[ "$gid" = '+str(os.getgid())+' ]')
  self.script=self.p/'boot.sh';self.script.write_text(s)
 def tearDown(self):self.tmp.cleanup()
 def write(self,n,s):p=self.c/n;p.write_text(s);p.chmod(0o600)
 def run_boot(self):return subprocess.run(['sh',str(self.script)],capture_output=True,text=True,timeout=5)
 def test_valid_config_preserves_secret_and_persistent_files(self):
  before={p.name:(p.stat().st_mtime_ns,p.read_bytes()) for p in self.c.iterdir()};r=self.run_boot();self.assertEqual(r.returncode,42,r.stderr+r.stdout);self.assertEqual(r.stdout,'started\n');self.assertNotIn('test-password',r.stderr);self.assertEqual(before,{p.name:(p.stat().st_mtime_ns,p.read_bytes()) for p in self.c.iterdir()});self.assertFalse((self.d/'plain.bootstrap.lock').exists())
 def test_nonprivate_secret_rejected_before_ram_copy(self):
  (self.c/'password').chmod(0o644);r=self.run_boot();self.assertEqual(r.returncode,90);self.assertEqual(list(self.d.iterdir()),[])
 def test_photo_setting_is_passed_to_worker_and_unknown_modes_rejected(self):
  self.write('config','a7c-plainftp-v2\n127.0.0.1\n21\nuploader\n/upload with spaces\n1\n')
  worker=self.files['plain-worker.sh'].replace('echo started','[ "$5" = 1 ] || exit 94\necho started')
  self.files['plain-worker.sh']=worker;self.write('plain-worker.sh',worker)
  self.write('manifest',''.join(hashlib.sha256(v.encode()).hexdigest()+' '+n+'\n' for n,v in self.files.items()))
  r=self.run_boot();self.assertEqual(r.returncode,42,r.stderr+r.stdout)
  self.write('config',(self.c/'config').read_text().replace('\n1\n','\n2\n'))
  self.assertEqual(self.run_boot().returncode,90)
 def test_no_owned_mount_or_busy_copy_rejected(self):
  self.mounts.write_text('other '+str(self.d)+' tmpfs rw 0 0\n');self.assertEqual(self.run_boot().returncode,90);self.assertEqual(list(self.d.iterdir()),[])
  self.mounts.write_text('a7c-upload-ram '+str(self.d)+' tmpfs rw 0 0\n');os.mkfifo(self.d/'source.fifo');self.assertEqual(self.run_boot().returncode,90);self.assertTrue((self.d/'source.fifo').is_fifo())
 def test_symlink_and_hash_mismatch_rejected(self):
  p=self.c/'password';p.unlink();p.symlink_to(self.c/'config');self.assertEqual(self.run_boot().returncode,90);p.unlink();self.write('password','test-password-never-log\n');self.write('relay','tampered');r=self.run_boot();self.assertEqual(r.returncode,90);self.assertNotIn('started',r.stdout);self.assertFalse((self.d/'plain.bootstrap.lock').exists())
 def test_extra_configuration_or_duplicate_manifest_rejected(self):
  p=self.c/'config';original=p.read_text();self.write('config',original+'unexpected\n');self.assertEqual(self.run_boot().returncode,90);self.write('config',original)
  p=self.c/'manifest';self.write('manifest',p.read_text()+p.read_text().splitlines()[0]+'\n');self.assertEqual(self.run_boot().returncode,90)
 def test_missing_discovery_cannot_silently_boot_old_eight_file_package(self):
  (self.c/'discovery').unlink()
  manifest=(self.c/'manifest').read_text()
  self.write('manifest',''.join(line+'\n' for line in manifest.splitlines() if not line.endswith(' discovery')))
  r=self.run_boot();self.assertEqual(r.returncode,90);self.assertIn('payload_count',r.stdout)
 def display(self, script):
  d=self.p/'display';d.mkdir(mode=0o700)
  for name,value in [('enabled','a7c-upload-display-v1\n'),('stage.sh',script),('stage.sha256',hashlib.sha256(script.encode()).hexdigest()+'\n')]:
   p=d/name;p.write_text(value);p.chmod(0o600)
  return d
 def test_optional_stage_failure_does_not_block_ftp_or_expose_password(self):
  self.display('#!/bin/sh\necho unavailable\nexit 90\n')
  r=self.run_boot();self.assertEqual(r.returncode,42,r.stderr+r.stdout)
  self.assertIn('started',r.stdout);self.assertIn('DISPLAY_OPTIONAL_STAGE_FAILED',r.stdout)
  self.assertNotIn('test-password',r.stdout+r.stderr+(self.d/'display-bootstrap.log').read_text())
 def test_stage_hash_mismatch_cannot_execute_and_stale_consumer_removed(self):
  d=self.display('#!/bin/sh\necho should-not-run\n');(d/'stage.sh').write_text('exit 91')
  (self.d/'upload-display.sh').write_text('stale')
  self.assertEqual(self.run_boot().returncode,42)
  self.assertFalse((self.d/'display-bootstrap.log').exists());self.assertFalse((self.d/'upload-display.sh').exists())
 def test_disabled_package_skips_stage_and_clears_stale_consumer(self):
  d=self.display('exit 91');(d/'enabled').unlink();(self.d/'upload-display.sh').write_text('stale')
  self.assertEqual(self.run_boot().returncode,42)
  self.assertFalse((self.d/'upload-display.sh').exists());self.assertFalse((self.d/'display-bootstrap.log').exists())
 def test_valid_optional_stage_completes_alongside_ftp(self):
  self.display('#!/bin/sh\necho staged\n')
  r=self.run_boot();self.assertEqual(r.returncode,42)
  self.assertEqual((self.d/'display-bootstrap.log').read_text(),'staged\n')
 def test_slow_optional_stage_overlaps_ftp_and_blocks_duplicate_boot(self):
  self.display('''#!/bin/sh
n=0
while [ ! -f "RELEASE" ]; do sleep .02; n=$((n+1)); [ "$n" -lt 150 ] || exit 90; done
'''.replace('RELEASE',str(self.d/'stage-release')))
  proc=subprocess.Popen(['sh',str(self.script)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   self.assertEqual(proc.wait(timeout=2),42)
   self.assertTrue((self.d/'display-bootstrap.lock').is_dir())
   # A second supervisor cannot overlap this still-running stage.
   duplicate=self.run_boot();self.assertEqual(duplicate.returncode,90)
   self.assertIn('busy',duplicate.stdout)
  finally:
   (self.d/'stage-release').touch()
   proc.communicate(timeout=3)
  self.assertFalse((self.d/'display-bootstrap.lock').exists())
  timings=(self.d/'plain-boot-timings.log').read_text()
  self.assertIn('op=worker_exec',timings);self.assertIn('op=display_end',timings)
if __name__=='__main__':unittest.main()

"""Real shell + C FTP/relay/receipt with a simulated native SD API.
Camera recording gates are independently exercised by test_media and baseline.
"""
import os,pathlib,re,subprocess,sys,unittest,hashlib
import test_ftp
SRC=test_ftp.SRC
RECEIVER=SRC.parents[2]/'nas/receiver'
sys.path.insert(0,str(RECEIVER))
from media import metadata
class WorkerIntegration(test_ftp.FTPTests):
 # Use the fixture only; inherited transport tests run in test_ftp.py.
 def setUp(self):
  super().setUp();self.d=self.root/'ram';self.d.mkdir();self.card=self.root/'card';self.card.mkdir()
  for name,files in [('plainftp',[SRC/'ftp.c',SRC.parent/'receipt/receipt.c']),('local-media',[SRC/'media.c']),('relay',[SRC.parent/'relay.c'])]:
   subprocess.run(['cc','-O2',*(['-DRELAY_SIZE_ONLY'] if name=='relay' else []),*map(str,files),'-o',str(self.d/name)],check=True)
  (self.root/'uptime').write_text('100.0 200.0\n')
  self.xml=(RECEIVER/'tests/metadata.xml').read_bytes();(self.root/'metadata').write_bytes(self.xml)
  (self.root/'owner-stat').write_text('123 (uploader) '+' '.join(['0']*19+['98765'])+'\n')
  self.identity=hashlib.sha256(f"a7c-file-v1:C0001.MP4:{len(self.content)}:2026-10-22T17:00:00".encode()).hexdigest()
  self.exe('bb','''#!/bin/sh
case "$1:$2" in tr:*) echo 'tr: applet not found' >&2; exit 127;; wc:-c) wc -c | xargs;; cat:/proc/uptime) echo '100.0 200.0';; *) exec "$@";; esac
''')
  self.exe('lease','''#!/bin/sh
echo start >> "$TEST_RAM/lease-starts"
touch "$TEST_RAM/lease.ready"
n=0
while [ ! -f "$TEST_RAM/lease.done" ]; do sleep .02; n=$((n+1)); [ "$n" -lt 1000 ] || exit 99; done
echo 'PROBE_DONE set=0 clear=0 guardian_status=0'
''')
  self.exe('monitor','''#!/usr/bin/env python3
import os,sys,pathlib,shutil,time
r=pathlib.Path(os.environ['TEST_RAM']);root=r.parent
if sys.argv[1]=='wait-ready':
 for _ in range(120):
  if (r/(sys.argv[2]+'.ready')).exists():raise SystemExit(0)
  time.sleep(.1)
 raise SystemExit(124)
if sys.argv[1]!='copy':raise SystemExit(90)
if sys.argv[3].endswith('.XML'):raise SystemExit('XML must not be read')
else:
 with (root/'source').open('rb') as src,(r/'source.fifo').open('wb') as dst:shutil.copyfileobj(src,dst)
''')
  self.exe('sd-monitor','''#!/usr/bin/env python3
import os,sys,pathlib,shutil,re
r=pathlib.Path(os.environ['TEST_RAM']);card=r.parent/'card';op=sys.argv[1]
if op in ('read','write','write-verify') and not re.fullmatch(r'U[0-9A-F]{6}[AB][.]RCP',sys.argv[3]):raise SystemExit(64)
if op=='root':
 print('IFSYS dir A:/')
 for f in sorted(card.iterdir()):print('[IFSYS]a----- %d 2026-10-19 10:00:00 %s'%(f.stat().st_size,f.name))
 print('MWF>')
elif op=='read':shutil.copyfile(card/sys.argv[3],r/'receipt.read')
elif op in ('write','write-verify'):
 dst=card/sys.argv[3]
 if dst.exists():raise SystemExit(90)
 data=(r/'receipt.write').read_bytes()
 if os.environ.get('TORN')=='1':data=data[:127]
 dst.write_bytes(data)
 if op=='write-verify':shutil.copyfile(dst,r/'receipt.read')
else:raise SystemExit(90)
''')
 def exe(self,name,body):p=self.d/name;p.write_text(body);p.chmod(0o700)
 def attempt(self,torn=False,source_unready=False,photo=None):
  old=(SRC.parent/'worker.sh').read_text();functions=''
  for name in ['log','uptime_seconds','wait_child','cleanup_completed_fifos']:
   functions+=re.search(r'^'+name+r'\(\) \{\n.*?^}\n',old,re.M|re.S)[0]
  new=(SRC/'worker.sh').read_text();functions+=new[new.index('ftp() {'):new.index('\nplain_run() {')]
  script=f'''B={self.d}/bb
D={self.d}
P={self.root}
HOST=127.0.0.1
PORT={self.port}
USER=test
ROOT=/
FTP_PASSWORD=only-test-secret
VIDEO=C0001.MP4
XML=C0001M01.XML
DRIVE=A
SIZE={len(self.content)}
XSIZE={len(self.xml)}
SOURCE_ROW="C0001.MP4 $SIZE C0001M01.XML $XSIZE 2026-10-22T17:00:00 2026-10-22T17:00:00"
'''+functions+'''\n# Native read-only and pre-write gates are exercised in test_snapshot.
source_checked() { return 0; }
source_same() { return 0; }
receipt_card_ready() { return 0; }
plain_attempt
exit $?
'''
  if photo:
   script=script.replace('VIDEO=C0001.MP4','VIDEO='+photo)
   script=script.replace('SOURCE_ROW="C0001.MP4 $SIZE C0001M01.XML $XSIZE 2026-10-22T17:00:00 2026-10-22T17:00:00"',f'SOURCE_ROW="{photo} $SIZE - 0 2026-10-22T17:00:00 -"')
  if source_unready:script=script.replace('source_checked() { return 0; }','source_checked() { return 1; }')
  script=script.replace('/bin/ash','/bin/sh').replace('/proc/$$/stat',str(self.root/'owner-stat')).replace('/proc/uptime',str(self.root/'uptime'))
  f=self.root/'attempt.sh';f.write_text(script)
  p=subprocess.run(['sh',str(f)],env=dict(os.environ,TEST_RAM=str(self.d),TORN='1' if torn else '0'),capture_output=True,timeout=25)
  if (self.d/'lease.log').exists():
   self.assertTrue((self.d/'lease.done').exists());self.assertIn('guardian_status=0',(self.d/'lease.log').read_text())
  return p
 def test_jpeg_raw_share_transport_and_receipts_but_never_dedup_each_other(self):
  for ext in ('JPG','ARW'):
   path='DCIM/100MSDCF/DSC00197.'+ext
   p=self.attempt(photo=path);self.assertEqual(p.returncode,0,p.stderr.decode())
   key=hashlib.sha256(f'a7c-file-v1:{path}:{len(self.content)}:2026-10-22T17:00:00'.encode()).hexdigest()
   self.assertEqual((self.remote/(key+'.'+ext)).read_bytes(),self.content)
   count=len(self.ops);p=self.attempt(photo=path);self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(len(self.ops),count)
  self.assertEqual(len(list(self.card.iterdir())),2)
 def test_photo_failure_leaves_no_receipt_and_successful_retry_skips_later(self):
  self.fault='truncate';path='DCIM/100MSDCF/DSC00197.JPG'
  p=self.attempt(photo=path);self.assertEqual(p.returncode,1,p.stderr.decode());self.assertFalse(list(self.card.iterdir()))
  self.fault=None;p=self.attempt(photo=path);self.assertEqual(p.returncode,0,p.stderr.decode())
  count=len(self.ops);self.assertEqual(self.attempt(photo=path).returncode,0);self.assertEqual(len(self.ops),count)
 def test_worker_commit_then_sd_skip_without_network(self):
  p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(len(list(self.card.iterdir())),1)
  for f in self.card.iterdir():self.assertEqual(len(f.read_bytes()),512)
  count=len(self.ops);p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(len(self.ops),count)
  self.assertNotIn('SD_SKIP',(self.d/'events.log').read_text());self.assertFalse((self.d/'source.fifo').exists());self.assertFalse((self.d/'metadata.xml').exists())
 def test_migrated_receipt_skips_without_xml_or_renaming_old_remote_video(self):
  row_id=self.identity;m=metadata(self.xml)
  self.identity=hashlib.sha256(f"{m['umid']}:{len(self.content)}:{m['xml_sha256']}".encode()).hexdigest()
  old_id=self.identity;self.assertEqual(self.put().returncode,0);record=self.commit();self.assertEqual(record.returncode,0)
  old=self.root/'old-receipt';old.write_bytes(record.stdout)
  args=[str(self.d/'plainftp'),'rekey','127.0.0.1',str(self.port),'test','/',old_id,str(len(self.content)),str(old),'-',row_id]
  changed=subprocess.run(args,capture_output=True,timeout=3);self.assertEqual(changed.returncode,0,changed.stderr)
  slot=subprocess.check_output([str(self.d/'plainftp'),'slot','127.0.0.1',str(self.port),'test','/',row_id],text=True).strip()
  (self.card/('U'+slot+'A.RCP')).write_bytes(changed.stdout);self.identity=row_id;count=len(self.ops)
  p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(len(self.ops),count)
  self.assertTrue((self.remote/(old_id+'.MP4')).exists());self.assertFalse((self.remote/(row_id+'.MP4')).exists())
  self.assertFalse((self.d/'metadata.xml').exists());self.assertFalse((self.d/'lease-starts').exists())
 def test_receipt_skip_does_not_start_upload_lease(self):
  p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode())
  count=(self.d/'lease-starts').read_text();self.exe('lease','#!/bin/sh\nexit 99\n')
  for name in ('lease.ready','lease.done','lease.log'):(self.d/name).unlink()
  p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode())
  self.assertEqual((self.d/'lease-starts').read_text(),count)
  self.assertFalse((self.d/'lease.ready').exists());self.assertFalse((self.d/'lease.done').exists())
 def test_worker_network_failure_has_no_sd_mark_then_retries(self):
  self.fault='truncate';p=self.attempt();self.assertEqual(p.returncode,1,p.stderr.decode());self.assertEqual(list(self.card.iterdir()),[])
  self.fault=None;p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(len(list(self.card.iterdir())),1)
 def test_unready_source_returns_separate_code_without_ftp_or_sd_io(self):
  count=len(self.ops);p=self.attempt(source_unready=True)
  self.assertEqual(p.returncode,75,p.stderr.decode())
  self.assertEqual(len(self.ops),count);self.assertEqual(list(self.card.iterdir()),[])
  self.assertFalse((self.d/'lease-starts').exists())
  p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode())
 def test_worker_torn_sd_receipt_uses_other_empty_slot_and_reconciles(self):
  p=self.attempt(torn=True);self.assertEqual(p.returncode,90,p.stderr.decode());self.assertEqual([f.stat().st_size for f in self.card.iterdir()],[127]);count=len(self.ops)
  p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(sorted(f.stat().st_size for f in self.card.iterdir()),[127,512]);self.assertEqual(len(self.ops),count)
 def enable_display(self,fail=False):
  self.exe('upload-display.sh','''#!/bin/sh
echo start >> "$TEST_RAM/display-events"
[ "$(cat "$TEST_RAM/display.active")" = "$1" ] || exit 99
'''+('exit 97\n' if fail else '''while [ -f "$TEST_RAM/display.active" ]; do sleep .01; done
[ ! -e "$TEST_RAM/lease.done" ] || exit 98
echo restored >> "$TEST_RAM/display-events"
'''))
 def test_display_lifetime_ends_before_lease_and_dedup_does_not_start(self):
  self.enable_display();p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode())
  self.assertEqual((self.d/'display-events').read_text(),'start\nrestored\n')
  self.assertFalse((self.d/'display.active').exists());self.assertFalse((self.d/'display.disabled').exists())
  p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode())
  self.assertEqual((self.d/'display-events').read_text(),'start\nrestored\n')
 def test_display_failure_does_not_fail_transfer_or_receipt(self):
  self.enable_display(fail=True);p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode())
  self.assertEqual(len(list(self.card.iterdir())),1);self.assertTrue((self.d/'display.disabled').exists())
  self.assertIn('DISPLAY_EXIT rc=97',(self.d/'events.log').read_text())
  self.assertFalse((self.d/'display.active').exists())
 def test_network_failure_clears_display_then_retry_starts_new_display(self):
  self.enable_display();self.fault='truncate';p=self.attempt();self.assertEqual(p.returncode,1,p.stderr.decode())
  self.assertFalse((self.d/'display.active').exists());self.assertFalse(list(self.card.iterdir()))
  self.fault=None;p=self.attempt();self.assertEqual(p.returncode,0,p.stderr.decode())
  self.assertEqual((self.d/'display-events').read_text(),'start\nrestored\nstart\nrestored\n')
# Avoid re-running inherited transport tests under the integration class.
for name in list(test_ftp.FTPTests.__dict__):
 if name.startswith('test_'):setattr(WorkerIntegration,name,None)
if __name__=='__main__':unittest.main()

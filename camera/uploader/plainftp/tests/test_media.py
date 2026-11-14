"""Real C local gates compared to existing Python parsers and damaged inputs."""
import hashlib,pathlib,subprocess,tempfile,unittest,sys
SRC=pathlib.Path(__file__).resolve().parents[1]
FIXTURES=pathlib.Path(__file__).resolve().parent/'fixtures'
from fixture_metadata import metadata
class MediaTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.build=tempfile.TemporaryDirectory();cls.bin=pathlib.Path(cls.build.name)/'media'
  subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror',str(SRC/'media.c'),'-o',str(cls.bin)],check=True)
  cls.xml=(FIXTURES/'metadata.xml').read_bytes();cls.status=(FIXTURES/'status.txt').read_bytes()
 @classmethod
 def tearDownClass(cls):cls.build.cleanup()
 def call(self,action,data,last='24'):
  with tempfile.TemporaryDirectory() as t:
   f=pathlib.Path(t)/'data';f.write_bytes(data)
   args=[action,str(f),last] if action=='identity' else [action,'B',str(f)]
   return subprocess.run([str(self.bin),*args],capture_output=True,timeout=3)
 def test_identity_matches_original_store_and_64bit_size(self):
  m=metadata(self.xml)
  for size in (24,2**32+1,274877906944):
   p=self.call('identity',self.xml,str(size));self.assertEqual(p.returncode,0,p.stderr)
   expected=hashlib.sha256(f"{m['umid']}:{size}:{m['xml_sha256']}".encode()).hexdigest()
   self.assertEqual(p.stdout.decode().strip(),expected)
 def test_xml_failure_cases(self):
  cases=[self.xml[:-40],self.xml.replace(b'</NonRealTimeMeta>',b'</Wrong>'),self.xml.replace(b'status="end"',b'status="increment"'),self.xml.replace(b'frameCount="71"',b'frameCount="72"'),self.xml.replace(b'ILCE-7C',b'ILCE-7M3'),self.xml.replace(b'<TargetMaterial umidRef=',b'<TargetMaterial value='),self.xml.replace(b'<Duration value="72"/>',b'<Duration value="72"/><Duration value="72"/>'),self.xml.replace(b'<Duration ',b'<Duration xmlns="foreign" '),self.xml.replace(b'<Duration ',b'<Duration value="1" '),self.xml.replace(b'<Duration ',b'<Duration x="&fake;" '),b'<!DOCTYPE x>'+self.xml,self.xml+b'<other/>']
  for data in cases:
   with self.subTest(prefix=data[:40]):self.assertNotEqual(self.call('identity',data).returncode,0)
 def row_key(self,row):
  return subprocess.run([str(self.bin),'row-identity',row],capture_output=True,timeout=3)
 def test_directory_identity_uses_only_video_name_length_and_timestamp(self):
  row='C0224.MP4 50342873 C0224M01.XML 2176 2026-10-22T17:00:00 2026-10-22T17:00:00'
  p=self.row_key(row);self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(p.stdout.decode().strip(),hashlib.sha256(b'a7c-file-v1:C0224.MP4:50342873:2026-10-22T17:00:00').hexdigest())
  for changed in [row.replace('50342873','50342874'),row.replace('C0224.MP4','C0225.MP4'),row.replace('T17:00:00','T17:00:01',1)]:
   self.assertNotEqual(self.row_key(changed).stdout,p.stdout)
  self.assertEqual(self.row_key(row.replace('2176','3333').rsplit(' ',1)[0]+' 2026-11-01T01:02:03').stdout,p.stdout)
 def test_directory_identity_rejects_malformed_or_extra_fields(self):
  row='C0224.MP4 50342873 C0224M01.XML 2176 2026-10-22T17:00:00 2026-10-22T17:00:00'
  for bad in ['',row+' extra',row.replace('50342873','-1'),row.replace('50342873','0'),row.replace('C0224.MP4','../x.MP4'),row.replace('2026-10-22T17:00:00','bad',1)]:
   self.assertNotEqual(self.row_key(bad).returncode,0,bad)
 def test_directory_strictness(self):
  p=self.call('dir',self.status);self.assertEqual(p.returncode,0);self.assertIn(b'C0193.MP4 24 C0193M01.XML 2174',p.stdout)
  for data in (self.status.replace(b'C0193M01.XML',b'C0194M01.XML'),self.status.replace(b'[IFSYS]a----- 24',b'[IFSYS]a----- -24'),self.status.replace(b'C0193.MP4',b'../bad.MP4'),self.status.replace(b'[IFSYS]a----- 2174',b'[IFSYS]a----- 20000')):
   self.assertNotEqual(self.call('dir',data).returncode,0)
 def test_newest_uses_timestamps_across_filename_wrap_and_stable_ties(self):
  rows=[]
  for number,stamp in [(9999,'2026-10-20 11:00:00'),(1,'2026-10-21 12:00:00'),(2,'2026-10-21 12:00:00')]:
   rows.extend([f'[IFSYS]a----- 24 {stamp} C{number:04d}.MP4',f'[IFSYS]a----- 2174 {stamp} C{number:04d}M01.XML'])
  data=('IFSYS dir B:/PRIVATE/M4ROOT/CLIP\r\n'+'\n'.join(rows)+'\nMWF>').encode()
  newest=self.call('newest',data);self.assertEqual(newest.returncode,0,newest.stderr)
  self.assertEqual([s.split()[0] for s in newest.stdout.decode().splitlines()],['C0002.MP4','C0001.MP4','C9999.MP4'])
  # Existing dir output remains canonical name order for legacy consumers.
  self.assertEqual([s.split()[0] for s in self.call('dir',data).stdout.decode().splitlines()],['C0001.MP4','C0002.MP4','C9999.MP4'])
 def test_newest_rejects_incomplete_and_duplicate_rows_before_output(self):
  for data in (self.status.replace(b'C0193M01.XML',b'C0194M01.XML'),self.status[:self.status.index(b'MWF>IFSYS info')]):
   p=self.call('newest',data);self.assertNotEqual(p.returncode,0);self.assertEqual(p.stdout,b'')
 def test_open_video_writer_blocks(self):
  self.assertEqual(self.call('info',self.status).returncode,0)
  changed=self.status.replace(b'D:\\PRIVATE\\M4ROOT\\MEDIAPRO.XML',b'D:\\PRIVATE\\M4ROOT\\CLIP\\C0193.MP4')
  self.assertNotEqual(self.call('info',changed).returncode,0)
  self.assertNotEqual(self.call('info',self.status.replace(b'/dev/mmca',b'/dev/unknown')).returncode,0)
 def photo_snapshot(self,folders=None):
  folders=folders or {'100MSDCF':[('DSC00197.JPG',24),('DSC00197.ARW',48)],'101MSDCF':[('DSC00197.JPG',32)]}
  out='IFSYS dir B:/DCIM\r\n'
  for folder in folders:out+=f'[IFSYS]-d---- 0 2026-11-05 10:00:00 {folder}\r\n'
  out+='MWF>\r\n'
  for folder,files in folders.items():
   out+=f'IFSYS dir B:/DCIM/{folder}\r\n'
   for file,size in files:out+=f'[IFSYS]a----- {size} 2026-11-05 10:00:00 {file}\r\n'
   out+='MWF>\r\n'
  return out.encode()
 def test_photos_enumerate_all_dcf_folders_and_keep_raw_jpeg_separate(self):
  p=self.call('photos',self.photo_snapshot());self.assertEqual(p.returncode,0,p.stderr)
  rows=p.stdout.decode().splitlines();self.assertEqual(len(rows),3)
  keys={self.row_key(row).stdout for row in rows};self.assertEqual(len(keys),3)
  self.assertTrue(all(self.row_key(row).returncode==0 for row in rows))
  self.assertIn('DCIM/100MSDCF/DSC00197.JPG 24 - 0 2026-11-05T10:00:00 -',rows)
 def test_photo_identity_binds_directory_size_and_timestamp(self):
  row='DCIM/100MSDCF/DSC00197.JPG 24 - 0 2026-11-05T10:00:00 -'
  first=self.row_key(row);self.assertEqual(first.returncode,0)
  for x in [row.replace('100MSDCF','101MSDCF'),row.replace('.JPG','.ARW'),row.replace(' 24 ',' 25 '),row.replace('T10:00:00','T10:00:01')]:
   self.assertNotEqual(self.row_key(x).stdout,first.stdout)
  for x in [row+' extra',row.replace('100MSDCF','../DCIM'),row.replace(' - 0 ',' x 0 '),row.replace('.JPG','.DNG')]:
   self.assertNotEqual(self.row_key(x).returncode,0)
 def test_mixed_queue_orders_by_timestamp_not_filename_or_file_type(self):
  rows=['C9999.MP4 24 C9999M01.XML 1 2026-11-03T10:00:00 2026-11-03T10:00:00',
        'DCIM/100MSDCF/DSC00001.JPG 24 - 0 2026-11-05T10:00:00 -',
        'C0001.MP4 24 C0001M01.XML 1 2026-11-04T10:00:00 2026-11-04T10:00:00']
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'rows';p.write_text('\n'.join(rows)+'\n')
   result=subprocess.run([str(self.bin),'order',str(p)],capture_output=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(result.stdout.decode().splitlines(),[rows[1],rows[2],rows[0]])
   p.write_text(rows[0]+'\ncorrupt\n')
   result=subprocess.run([str(self.bin),'order',str(p)],capture_output=True)
   self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)
 def test_photos_skip_thumbnails_and_other_files_and_require_complete_replies(self):
  data=self.photo_snapshot({'100MSDCF':[('DSC00197.JPG',24),('DSC00197.THM',8)]})
  p=self.call('photos',data);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(len(p.stdout.splitlines()),1)
  for bad in [data[:data.rfind(b'MWF>')],data.replace(b'DSC00197.JPG',b'DSC00197.JPG\r\n[IFSYS]a----- 24 2026-11-05 10:00:00 DSC00197.JPG')]:
   p=self.call('photos',bad);self.assertNotEqual(p.returncode,0);self.assertFalse(p.stdout)
 def test_photo_writers_block_but_readers_do_not(self):
  writing=self.status.replace(b'D:\\PRIVATE\\M4ROOT\\MEDIAPRO.XML',b'D:\\DCIM\\100MSDCF\\DSC00197.JPG')
  self.assertNotEqual(self.call('info-photos',writing).returncode,0)
  self.assertEqual(self.call('info',writing).returncode,0)
 def test_card_identity_change_invalidates_signature(self):
  a=self.call('info',self.status);b=self.call('info',self.status.replace(b'39 01 C3 00 F5 4D 80 38',b'38 01 C3 00 F5 4D 80 38'))
  self.assertEqual(a.returncode,0);self.assertEqual(b.returncode,0);self.assertNotEqual(a.stdout,b.stdout)
 def test_missing_native_completion_rejected(self):
  for action,marker in [('dir',b'MWF>IFSYS info'),('info',b'MWF>')]:
   data=self.status[:self.status.rfind(marker)]
   self.assertNotEqual(self.call(action,data).returncode,0)
 def root_exists(self,rows,target='UABC123A.RCP'):
  with tempfile.TemporaryDirectory() as temp:
   source=pathlib.Path(temp)/'root'
   source.write_text('IFSYS dir B:/\r\n'+'\r\n'.join(rows)+'\r\nMWF>')
   return subprocess.run([str(self.bin),'exists','B',target,str(source)],capture_output=True,timeout=3).returncode
 def test_root_long_directory_names_do_not_block_receipts(self):
  rows=['[IFSYS]-d-sh- 131072 2026-10-27 18:46:05 System Volume Information',
        '[IFSYS]-d---- 131072 2026-10-27 18:46:05 相机资料 备份',
        '[IFSYS]-d--h- 131072 2026-10-27 07:35:57 .fseventsd']
  self.assertEqual(self.root_exists(rows),10)
  receipt='[IFSYS]a----- 512 2026-10-27 18:46:05 UABC123A.RCP'
  self.assertEqual(self.root_exists(rows+[receipt]),0)
  self.assertEqual(self.root_exists(rows+[receipt,receipt]),90)
  self.assertEqual(self.root_exists(rows+[receipt.replace('512','513')]),90)
  self.assertEqual(self.root_exists(rows+[receipt+' extra']),10)
 def test_interleaved_native_console_noise_is_retryable_never_absent(self):
  # Observed on the camera 2026-11-05: an asynchronous MWF message split a row.
  receipt='[IFSYS]a----- 512 2026-10-27 18:46:05 UABC123A.RCP'
  other='[IFSYS]a----- 512 2026-11-03 11:03:26 UDA75F6A.RCP'
  split=['[IFSYS]a----- 512 2026-11-03 11:03:26 UDA75F6MWF]  [RsrcAcsr] already Acquired!',':A.RCP']
  self.assertEqual(self.root_exists([receipt,other]),0)
  self.assertEqual(self.root_exists([other]),10)
  self.assertEqual(self.root_exists([receipt]+split),75)
  self.assertEqual(self.root_exists(split),75)        # could have hidden our receipt
  self.assertEqual(self.root_exists(['[IFSYS]garbage']),75)
  self.assertEqual(self.root_exists(['[MWF]  [RsrcAcsr] Not acquired!']),75)
  with tempfile.TemporaryDirectory() as temp:
   truncated=pathlib.Path(temp)/'root';truncated.write_text('IFSYS dir B:/\r\n'+receipt)
   self.assertEqual(subprocess.run([str(self.bin),'exists','B','UABC123A.RCP',str(truncated)],timeout=3).returncode,75)
   self.assertEqual(subprocess.run([str(self.bin),'exists','B','UABC123A.RCP',str(truncated)+'.missing'],timeout=3).returncode,75)
if __name__=='__main__':unittest.main()

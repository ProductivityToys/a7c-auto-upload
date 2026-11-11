"""Read-only profile binding and bounded hints; never exercises media writes."""
from pathlib import Path
import os
import time
import struct
import subprocess
import tempfile
import unittest
SRC=Path(__file__).resolve().parents[1]
class RecorderProbeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.proc=cls.root/'proc';cls.proc.mkdir();cls.pid=cls.proc/'162';cls.pid.mkdir();cls.binary=cls.root/'probe'
  subprocess.run(['cc','-O2','-fno-builtin','-DA7C_LINK_INDEX="'+str(cls.root/'link-index')+'"','-DA7C_PROC_ROOT="'+str(cls.proc)+'"','-DA7C_CANCEL_PATH="'+str(cls.root/'cancel')+'"','-DA7C_UPLOADER_STOP="'+str(cls.root/'uploader-stop')+'"',str(SRC/'recorder_probe.c'),'-o',str(cls.binary)],check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):
  (self.root/'link-index').write_text('7\n')
  (self.root/'cancel').unlink(missing_ok=True)
  (self.root/'uploader-stop').unlink(missing_ok=True)
  (self.pid/'comm').write_text('im.elf\n');self.base=0x10000;self.core=0x2000000
  (self.pid/'maps').write_text('00010000-01550000 r-xp 00000000 00:00 1 /usr/lib/libmpr.so\n02000000-02010000 rw-p 00000000 00:00 0\n')
  with (self.pid/'mem').open('wb') as f:
   f.seek(self.base+0x8a9fe4);f.write(bytes.fromhex('074b80b500af1b681bb90648f0f75cff'))
   f.seek(self.base+0x1536438);f.write(struct.pack('<I',self.core))
   for i in range(4):
    f.seek(self.core+0x16ac+i*0x108);data=bytearray(0x104);struct.pack_into('<I',data,0,i);data[4]=int(i<2);struct.pack_into('<I',data,8,7);struct.pack_into('<I',data,0xf0,1);f.write(data)
 def run_probe(self,pid='162'):
  return subprocess.run([str(self.binary),pid],capture_output=True,text=True,timeout=2)
 def test_profiled_sample_has_no_file_changes(self):
  mem=self.pid/'mem';before=mem.stat();p=self.run_probe();self.assertEqual(p.returncode,0,p.stderr)
  self.assertIn('line=0 active=1 index=0 type=7 state=1 count1=0 count2=0',p.stdout)
  after=mem.stat();self.assertEqual((before.st_size,before.st_mtime_ns),(after.st_size,after.st_mtime_ns))
 def test_name_code_and_mapping_mismatch_publish_nothing(self):
  for mode in ['comm','code','mapping']:
   self.setUp()
   if mode=='comm':(self.pid/'comm').write_text('other\n')
   elif mode=='code':
    with (self.pid/'mem').open('r+b') as f:f.seek(self.base+0x8a9fe4);f.write(b'X')
   else:(self.pid/'maps').write_text('00010000-01550000 r-xp 00000000 00:00 1 /wrong/libmpr.so\n')
   p=self.run_probe();self.assertEqual(p.returncode,95,mode);self.assertEqual(p.stdout,'')
 def test_null_unmapped_and_overflow_pointer_rejected(self):
  for ptr in [0,0x3000000,0xfffff000]:
   with (self.pid/'mem').open('r+b') as f:f.seek(self.base+0x1536438);f.write(struct.pack('<I',ptr))
   p=self.run_probe();self.assertEqual(p.returncode,95);self.assertEqual(p.stdout,'')
 def test_strict_pid_and_duplicate_library(self):
  for pid in ['0','1','-1','162/x','9999999999']:
   p=self.run_probe(pid);self.assertEqual(p.returncode,64)
  with (self.pid/'maps').open('a') as f:f.write('03000000-04550000 r-xp 00000000 00:00 1 /usr/lib/libmpr.so\n')
  p=self.run_probe();self.assertEqual(p.returncode,95)
 def test_native_ftp_master_reads_only_validated_view_cache(self):
  base=0x3000000
  with (self.pid/'maps').open('a') as f:
   f.write('03000000-03ae4000 r-xp 00000000 00:00 2 /usr/lib/viewUnified2.so\n'
           '03ae4000-03da0000 rw-p 00ae4000 00:00 2 /usr/lib/viewUnified2.so\n')
  def put(offset,data):
   with (self.pid/'mem').open('r+b') as f:
    f.seek(base+offset);f.write(data)
  put(0x704f3a,bytes.fromhex('40f2011180f6b4e7042021467bf6c2e4'))
  put(0x56bf60,bytes.fromhex('104be3581b689d4210da0f4b1822e358'))
  put(0xcce200,struct.pack('<I',base+0xd3cf98))
  def read_switch():
   p=subprocess.run([str(self.binary),'162','ftp-master'],capture_output=True,text=True,timeout=2)
   return p.returncode,p.stdout
  for value,expected in [(2,(0,'on\n')),(1,(0,'off\n')),(0,(95,'')),(3,(95,''))]:
   put(0xd3cf98,struct.pack('<I',value))
   self.assertEqual(read_switch(),expected)
  put(0xd3cf98,struct.pack('<I',2))
  put(0xcce200,struct.pack('<I',base+0xd3cf9c))
  self.assertEqual(read_switch(),(95,''))
  put(0xcce200,struct.pack('<I',base+0xd3cf98))
  put(0x56bf60,b'X')
  self.assertEqual(read_switch(),(95,''))
 def test_watch_only_emits_changes_and_reports_cpu_time(self):
  p=subprocess.Popen([str(self.binary),'162','watch','2'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  time.sleep(.3)
  with (self.pid/'mem').open('r+b') as f:f.seek(self.core+0x179c);f.write(struct.pack('<I',3))
  out,err=p.communicate(timeout=5);self.assertEqual(p.returncode,0,err)
  self.assertEqual(out.count('A7C_RECORDER_SAMPLE_V1'),2)
  self.assertIn('state=3',out);self.assertIn('A7C_RECORDER_WATCH_DONE rc=0',out);self.assertIn('cpu_ms=',out)
 def test_cancel_and_watch_limits(self):
  (self.root/'cancel').touch()
  p=subprocess.run([str(self.binary),'162','watch','1800'],capture_output=True,text=True,timeout=1)
  self.assertEqual(p.returncode,0);self.assertIn('samples=1',p.stdout)
  for args in [('watch','0'),('watch','1801'),('watch','-1'),('other','2')]:
   p=subprocess.run([str(self.binary),'162',*args],capture_output=True);self.assertEqual(p.returncode,64)
 def movie(self,state,count=0):
  for i in range(2):
   with (self.pid/'mem').open('r+b') as f:
    f.seek(self.core+0x16b4+i*0x108);f.write(struct.pack('<I',256))
    f.seek(self.core+0x179c+i*0x108);f.write(struct.pack('<I',state))
    f.seek(self.core+0x17a8+i*0x108);f.write(struct.pack('<I',count))
 def test_wait_quiet_timeout_and_busy_timeout_are_distinct(self):
  self.movie(1)
  p=subprocess.run([str(self.binary),'162','wait','1','7'],capture_output=True,text=True,timeout=3)
  self.assertEqual(p.returncode,0);self.assertIn('WAIT_DONE rc=0',p.stdout)
  self.movie(3,1)
  p=subprocess.run([str(self.binary),'162','wait','1','7'],capture_output=True,text=True,timeout=3)
  self.assertEqual(p.returncode,11);self.assertIn('WAIT_DONE rc=11',p.stdout)
 def still(self,state,count=0):
  self.movie(state,count)
  with (self.pid/'mem').open('r+b') as f:
   f.seek(self.core+0x16b4);f.write(struct.pack('<I',1))
   f.seek(self.core+0x16ac+0x108+4);f.write(b'\0')
 def test_still_standby_is_quiet_and_active_still_is_busy(self):
  self.still(1)
  p=subprocess.run([str(self.binary),'162','wait','1','7'],capture_output=True,text=True,timeout=3)
  self.assertEqual(p.returncode,0,p.stderr)
  self.still(3,1)
  p=subprocess.run([str(self.binary),'162','wait','1','7'],capture_output=True,text=True,timeout=3)
  self.assertEqual(p.returncode,11,p.stderr)
 def test_still_completion_wakes_scan_without_treating_busy_as_idle(self):
  self.still(3,1)
  p=subprocess.Popen([str(self.binary),'162','wait','5','7'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   time.sleep(1.2);self.assertIsNone(p.poll());self.still(1)
   out,err=p.communicate(timeout=3);self.assertEqual(p.returncode,10,err)
  finally:
   if p.poll() is None:p.kill();p.communicate()
 def test_wait_does_not_wake_at_record_start_but_wakes_after_finish(self):
  self.movie(1)
  p=subprocess.Popen([str(self.binary),'162','wait','5','7'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   time.sleep(.3);self.movie(3,1);time.sleep(1.2);self.assertIsNone(p.poll())
   self.movie(4,1);time.sleep(1.1);self.assertIsNone(p.poll())
   self.movie(1);out,err=p.communicate(timeout=3)
   self.assertEqual(p.returncode,10,err);self.assertIn('WAIT_DONE rc=10',out)
   self.assertNotIn('A7C_RECORDER_SAMPLE',out)
  finally:
   if p.poll() is None:p.kill();p.communicate()
 def test_wait_cancel_unknown_mode_and_strict_limit(self):
  self.movie(1);(self.root/'uploader-stop').touch()
  p=subprocess.run([str(self.binary),'162','wait','30','7'],capture_output=True,text=True,timeout=1)
  self.assertEqual(p.returncode,20)
  (self.root/'uploader-stop').unlink();self.movie(99)
  p=subprocess.run([str(self.binary),'162','wait','30','7'],capture_output=True,text=True,timeout=1)
  self.assertEqual(p.returncode,95)
  for args in [('wait','0'),('wait','31'),('wait','-1')]:
   p=subprocess.run([str(self.binary),'162',*args,'7'],capture_output=True);self.assertEqual(p.returncode,64)
 def test_network_generation_changed_before_wait_is_not_missed(self):
  self.movie(1);(self.root/'link-index').write_text('8\n')
  p=subprocess.run([str(self.binary),'162','wait','30','7'],capture_output=True,text=True,timeout=2)
  self.assertEqual(p.returncode,12,p.stderr);self.assertIn('link_index=8',p.stdout)
 def test_network_generation_change_interrupts_existing_wait(self):
  self.movie(1)
  p=subprocess.Popen([str(self.binary),'162','wait','30','7'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   time.sleep(.2);(self.root/'link-index').write_text('9\n')
   out,err=p.communicate(timeout=3)
   self.assertEqual(p.returncode,12,err);self.assertIn('link_index=9',out)
  finally:
   if p.poll() is None:p.kill();p.communicate()
 def test_missing_interface_is_a_change_and_invalid_generation_is_rejected(self):
  self.movie(1);(self.root/'link-index').unlink()
  p=subprocess.run([str(self.binary),'162','wait','1','7'],capture_output=True,text=True,timeout=2)
  self.assertEqual(p.returncode,12);self.assertIn('link_index=0',p.stdout)
  p=subprocess.run([str(self.binary),'162','wait','1','0'],capture_output=True,text=True,timeout=3)
  self.assertEqual(p.returncode,0)
  for value in ('','-1','7x','2147483648','9999999999'):
   p=subprocess.run([str(self.binary),'162','wait','1',value],capture_output=True,timeout=2)
   self.assertEqual(p.returncode,64,value)
if __name__=='__main__':unittest.main()

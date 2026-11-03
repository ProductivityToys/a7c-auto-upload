"""Normal file-status labels must not trip the native copy-error gate."""
import ctypes,pathlib,subprocess,tempfile,unittest
SRC=pathlib.Path(__file__).resolve().parents[1]
class MonitorResultTests(unittest.TestCase):
 def test_native_error_variants_and_normal_information(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);source=d/'wrapper.c';lib=d/'result.so'
   source.write_text('#include <string.h>\n#include "monitor_result.h"\nint classify(int copy,const char *s){return a7c_command_result(copy,s);}\nint complete(const char *s,const char *marker){return a7c_completed_reply(s,marker,"MWF>")!=0;}\n')
   subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror','-I',str(SRC),str(source),'-o',str(lib)],check=True)
   dll=ctypes.CDLL(str(lib));done=dll.complete;done.argtypes=[ctypes.c_char_p,ctypes.c_char_p];done.restype=ctypes.c_int
   for cmd in (b'IFSYS cp B:/PRIVATE/M4ROOT/CLIP/C0190M01.XML /setting/a7c-uploader/ram/metadata.xml',b'IFSYS dir B:/PRIVATE/M4ROOT/CLIP'):
    marker=cmd+b'\r\n';local_echo=cmd+b'\n\r\nMWF>'
    self.assertEqual(done(local_echo,marker),0)
    self.assertEqual(done(local_echo+marker,marker),0)
    self.assertEqual(done(local_echo+marker+b'body\r\nMWF>',marker),1)
   fn=dll.classify;fn.argtypes=[ctypes.c_int,ctypes.c_char_p];fn.restype=ctypes.c_int
   normal=b'******** Fsys - IFSYS\nopen file info :\n  file handle = 0x123\nMWF>'
   for copy in (0,1):self.assertEqual(fn(copy,normal),0)
   for error in (b"Can't open file B:/PRIVATE/M4ROOT/CLIP/C0190.MP4",b"Can\\'t open file /setting/a7c-uploader/ram/source.fifo",b'illegal file name bad'):
    self.assertEqual(fn(1,error),73)
    self.assertEqual(fn(0,error),0)
   self.assertEqual(fn(1,b'IFSYS cp B:/PRIVATE/M4ROOT/CLIP/C0190.MP4 /setting/a7c-uploader/ram/source.fifo\r\nMWF>'),0)
if __name__=='__main__':unittest.main()

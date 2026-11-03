#!/usr/bin/env python3
"""Verify original stage-record layout without enabling or changing camera state."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image,IMAGES
from power_receivers_firmware import Machine

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--research',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();path,sha=IMAGES['obj'];image=Image(a.research/path,sha)
 assert 0x898390+image.u32(0x8983f0)==0x1488e84
 labels=[]
 for pc,lit,label in ((0x89f538,0x89f580,b'updateFrame     '),(0x89f554,0x89f584,b'notifyDraw      '),(0x89f564,0x89f588,b'drawFramebuffer ')):
  addr=pc+4+image.u32(lit);assert image.read(addr,16)==label;labels.append(label.decode())
 cases=[]
 for enabled,index in ((False,0),(True,0),(True,1)):
  m=Machine(image=image);buf,label=m.BASE+0x100,m.BASE+0x200
  m.u.mem_write(buf,b'\xa5'*100);m.u.mem_write(label,b'drawFramebuffer ')
  m.write(0x1488e84,buf if enabled else 0)
  def timestamp(dst,*_):
   m.write(dst,123);m.write(dst+4,456);m.events.append(['timestamp']);return 0
  m.hooks[0x8981ac]=timestamp
  events=m.run(0x898380,index,label)
  actual=bytes(m.u.mem_read(buf,100));expected=bytearray(b'\xa5'*100)
  if enabled:
   import struct
   start=12+index*24
   expected[start:start+24]=struct.pack('<II',123,456)+b'drawFramebuffer '
  assert actual==expected
  assert events==([['timestamp']] if enabled else [])
  cases.append({'trace_enabled':enabled,'index':index,'events':events})
 a.output.write_text(json.dumps({'firmware':'2.00','sha256':sha,'camera_access':False,'cases':cases,'labels':labels,'meaning':'Stage entry only; no completion fence. Clock boundary mocked.'},indent=2)+'\n')
 print(f'Passed {len(cases)} original-writer cases')
if __name__=='__main__':main()

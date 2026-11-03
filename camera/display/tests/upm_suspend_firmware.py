#!/usr/bin/env python3
"""Replay pinned 2.00 UPM phase dispatch offline; never contacts a camera.

OSAL, logging, front-end work and dmm are mocked. This tests phase gates and
message construction, not the front-end implementation or GPU completion.
"""
from pathlib import Path
import hashlib,struct,json
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2
import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--research', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
P = args.research / 'evidence/camera-2.00-power/usr__kmod__upm.ko'
assert hashlib.sha256(P.read_bytes()).hexdigest()=='cb15ec61082eec31f554076947a8aa88083ba7e4ecd22a1cf34014af2341343f'
class Machine:
    def __init__(self):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.calls={};self.events=[];self.sections={};self.names={}
        self.u.mem_map(0x3000000,0x20000);self.msg=0x3001004;self.out=0x3002004;self.stop=0x3003000;self.stack=0x301f000
        with P.open('rb') as f:
            e=ELFFile(f)
            for i,s in enumerate(e.iter_sections()):
                if s['sh_flags']&2:
                    b=0x100000+i*0x100000;self.sections[i]=b;self.names[s.name]=b
                    self.u.mem_map(b,(s['sh_size']+4095)&~4095)
                    if s['sh_type']!='SHT_NOBITS':self.u.mem_write(b,s.data())
            for s in e.iter_sections():
                if s['sh_type']!='SHT_REL' or s['sh_info'] not in self.sections:continue
                syms=e.get_section(s['sh_link']);base=self.sections[s['sh_info']]
                for r in s.iter_relocations():
                    a=base+r['r_offset'];sym=syms.get_symbol(r['r_info_sym']);typ=r['r_info_type']
                    if typ==2:
                        if sym['st_shndx'] not in self.sections:continue  # Unused external data; accessing it will fault.
                        self.write(a,self.word(a)+self.sections[sym['st_shndx']]+sym['st_value'])
                    elif typ in (28,29):self.calls[a]=sym.name
        self.base=self.names['.text'];self.state=self.names['.data']+0x70+0x50
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def write(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def word(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
    def hook(self,u,a,size,data):
        off=a-self.base
        if a==self.stop:u.emu_stop();return
        if off in (0x8fc4,0x8f30):
            u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if a not in self.calls:return
        name=self.calls[a];r0=u.reg_read(UC_ARM_REG_R0);r1=u.reg_read(UC_ARM_REG_R1)
        if name.startswith('k_upm_off_factor_handler_'):
            dest={'k_upm_off_factor_handler_inactive':0xa424,'k_upm_off_factor_handler_inacting_im2':0xbb80,'k_upm_off_factor_handler_inacting_im':0xa794,'k_upm_off_factor_handler_inacting_app2':0xa99c}[name]
            u.reg_write(UC_ARM_REG_LR,a+4);u.reg_write(UC_ARM_REG_PC,self.base+dest);return
        if name=='osal_valloc_msg_wait':self.write(r1,self.out)
        elif name=='osal_snd_sync_msg':self.events.append({'send_queue':hex(r0),'words':[hex(self.word(r1+i)) for i in (0,4,8,12)]})
        elif name=='dmm_pre_suspend':self.events.append({'call':name})
        else:assert name in ('osal_wai_sem_tmo','osal_sig_sem','osal_free_msg','k_upm_snd_hcrn_ura','k_upm_kikilog_A_E2_pon_ruiseki_stop','upm_off_timetag_num'),name
        u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,a+4)
    def run(self,state,words):
        self.events=[];self.write(self.state,state)
        for i,v in enumerate(words):self.write(self.msg+i*4,v)
        for r,v in ((UC_ARM_REG_SP,self.stack),(UC_ARM_REG_LR,self.stop),(UC_ARM_REG_R0,self.msg),(UC_ARM_REG_R1,0)):
            self.u.reg_write(r,v)
        self.u.emu_start(self.base+0xbe60,self.stop,count=2000)
        assert self.u.reg_read(UC_ARM_REG_PC)==self.stop
        return {'input_state':hex(state),'input':[hex(x) for x in words],'output_state':hex(self.word(self.state)),'events':self.events.copy()}
m=Machine();cases=[]
for state,words,new,op,queue in (
    (0x13,[0x920144,1,0x920168,0],0x12,0x920143,0x920169),
    (0x12,[0x920144,1,0x920169,0],0x14,0x920147,0x920168),
    (0x14,[0x92014a,0,0,0],0x21,0x92014b,0x920169),
    (0x21,[0x920144,2,0x920169,0],0x21,0x920143,0x920195),
    (0x21,[0x920144,0,0x920195,0],0x21,0x92014d,0x920169),
    (0x21,[0x92014e,0,0,0],0x22,0x92014f,0x920169),
    (0x21,[0x920144,1,0x920169,0],0x21,None,None),
    (0x21,[0x920144,2,0x123456,0],0x21,None,None)):
    r=m.run(state,words);assert int(r['output_state'],16)==new,r
    sends=[x for x in r['events'] if 'send_queue'in x]
    assert len(sends)==(0 if op is None else 1),r
    if op is not None:assert int(sends[0]['words'][0],16)==op and int(sends[0]['send_queue'],16)==queue,r
    cases.append(r)
assert cases[5]['events'][0]=={'call':'dmm_pre_suspend'}
result={'firmware':'ILCE-7C 2.00','upm_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'camera_access':False,'scope':'Actual ARM dispatcher and four phase handlers; OSAL, front-end operations, dmm and logging mocked. No physical device execution or GPU completion inference.','cases':cases}
with args.output.open('x') as output:
    output.write(json.dumps(result, indent=2) + '\n')
print('Passed', len(cases), 'offline cases:', args.output)

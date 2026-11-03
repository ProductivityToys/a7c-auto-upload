#!/usr/bin/env python3
"""Execute pinned Sony IM lifecycle instructions offline (requires Unicorn).

No camera access. Native dispatcher, callback wrapper, counters and completion
handlers run unchanged; dynamic lookup, logging and the module callback are
explicit stubs. This tests the IM protocol, not GPU completion or real sleep.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_SP

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_im_modules import IM, IMDB, audit
from audit_ui_contract import Image, IMAGES


class Machine:
    NODE, DESC, NAME, CALLBACK, STOP = 0x300000, 0x300100, 0x300200, 0x300300, 0x300400

    def __init__(self, image, callback_return=0, missing_symbol=False):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        pages = set()
        for segment in image.loads:
            start, length = segment['p_vaddr'], segment['p_memsz']
            pages.update(range(start & ~4095, (start + length + 4095) & ~4095, 4096))
        for page in sorted(pages):
            self.uc.mem_map(page, 4096)
        for segment in image.loads:
            self.uc.mem_write(segment['p_vaddr'], segment.data())
        self.uc.mem_map(self.NODE, 0x10000)
        self.uc.mem_map(0x400000, 0x10000)
        self.callback_return = callback_return
        self.missing_symbol = missing_symbol
        self.lookup_pending = False
        self.calls = 0
        self.sent = []
        self.freed = 0
        self.alloc_error = self.send_error = 0
        self.write(self.NODE + 8, self.DESC)
        self.write(self.NODE + 16, 123)
        self.uc.mem_write(self.NAME, b'test_callback\0')
        self.write(self.DESC, 0x20000003)
        self.write(self.DESC + 12, 2031)
        for offset in (0x1c, 0x20, 0x24, 0x28):
            self.write(self.DESC + offset, self.NAME)
        self.uc.hook_add(UC_HOOK_CODE, self.hook)

    def read(self, address):
        return struct.unpack('<I', self.uc.mem_read(address, 4))[0]

    def write(self, address, value):
        self.uc.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def ret(self, value):
        self.uc.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
        self.uc.reg_write(UC_ARM_REG_PC, self.uc.reg_read(UC_ARM_REG_LR))

    def hook(self, uc, address, size, data):
        if address == self.STOP:
            uc.emu_stop()
        elif address == 0xaf58:  # Sony log sink only
            self.ret(0)
        elif address == 0x9148:  # dlerror: initial clear then lookup result
            failed = self.lookup_pending and self.missing_symbol
            self.lookup_pending = False
            self.ret(self.NAME if failed else 0)
        elif address == 0x9204:  # dlsym
            self.lookup_pending = True
            self.ret(self.CALLBACK | 1)
        elif address == self.CALLBACK:
            self.calls += 1
            self.ret(self.callback_return)
        elif address == 0x9020:  # IMDB_find_entry (only our descriptor)
            assert uc.reg_read(UC_ARM_REG_R0) == 2031
            self.ret(self.DESC)
        elif address == 0xbcc4:  # loaded-list lookup, one synthetic module
            assert uc.reg_read(UC_ARM_REG_R0) == self.DESC
            self.ret(self.NODE)
        elif address == 0x110dc98:  # original libObj sender's allocation PLT
            assert uc.reg_read(UC_ARM_REG_R0) == 0x94016a
            assert uc.reg_read(UC_ARM_REG_R2) == 16 and uc.reg_read(UC_ARM_REG_R3) == 1
            self.write(uc.reg_read(UC_ARM_REG_R1), self.NODE + 0x604)
            self.ret(self.alloc_error)
        elif address == 0x110f3b8:  # asynchronous queue boundary, no synchronous RPC
            assert uc.reg_read(UC_ARM_REG_R0) == 0x94016a
            p = uc.reg_read(UC_ARM_REG_R1)
            assert p == self.NODE + 0x604
            self.sent.append([self.read(p + offset) for offset in (-4, 0, 4, 8, 12)])
            self.ret(self.send_error)
        elif address == 0x110ea54:
            assert uc.reg_read(UC_ARM_REG_R0) == 0x94016a
            self.freed += 1
            self.ret(0)

    def run(self, address, arg=0, arg1=0):
        self.uc.reg_write(UC_ARM_REG_SP, 0x40f000)
        self.uc.reg_write(UC_ARM_REG_LR, self.STOP | 1)
        self.uc.reg_write(UC_ARM_REG_R0, arg)
        self.uc.reg_write(UC_ARM_REG_R1, arg1)
        self.uc.emu_start(address | 1, self.STOP, count=10000)
        assert self.uc.reg_read(UC_ARM_REG_PC) == self.STOP, 'Instruction budget exhausted'
        return self.uc.reg_read(UC_ARM_REG_R0)


def verify(image, obj):
    results = []
    for name, entry, getter, counter, pending, done, acknowledgement in (
        ('inact', 0xb23c, 0xae3c, 0x1550c, 3, 4, 0xae84),
        ('act', 0xb2a0, 0xae4c, 0x15510, 5, 2, 0xae98),
    ):
        for return_value in (0, 1, -1):
            m = Machine(image, callback_return=return_value)
            m.run(entry, m.NODE)
            assert m.calls == 1 and m.read(m.NODE + 20) == pending
            assert m.run(getter) == m.read(counter) == 1
            m.run(acknowledgement, 2031)
            assert m.read(m.NODE + 20) == done and m.run(getter) == 0
            results.append(dict(callback=name, return_value=return_value,
                                pending_before_ack=1, pending_after_ack=0,
                                state_before_ack=pending, state_after_ack=done))
        for module_type in (0x20000001, 0x20000002):
            m = Machine(image)
            m.write(m.DESC, module_type)
            m.run(entry, m.NODE)
            assert m.calls == 0 and m.run(getter) == 0
        m = Machine(image, missing_symbol=True)
        m.run(entry, m.NODE)
        assert m.calls == 0 and m.run(getter) == 0
    # Suspend/resume use different dispatch paths; they do not add async debt.
    for entry in (0xb1ec, 0xb140):
        m = Machine(image)
        m.run(entry, m.NODE)
        assert m.calls == 1 and m.read(0x1550c) == m.read(0x15510) == 0
    # Independent original sender: full header/body and ownership on failure.
    for operation in (0x940122, 0x940123):
        for alloc_error, send_error in ((0, 0), (-7, 0), (0, -8)):
            m = Machine(image)
            m.uc.mem_map(0x1930000, 4096)
            m.uc.mem_map(0x110d000, 0x3000)
            m.uc.mem_write(0x1930c7c, obj.read(0x930c7c, 0x58))
            m.alloc_error, m.send_error = alloc_error, send_error
            rc = m.run(0x1930c88, operation, 2031)
            assert rc == ((alloc_error or send_error) & 0xffffffff)
            assert m.sent == ([] if alloc_error else [[0x94016a, operation, 2031, 0, 0]])
            assert m.freed == int(bool(send_error))
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    image, database = Image(a.research / IM[0], IM[1]), Image(a.research / IMDB[0], IMDB[1])
    obj = Image(a.research / IMAGES['obj'][0], IMAGES['obj'][1])
    try:
        descriptor = next(row for row in audit(image, database)['entries'] if row['id'] == 2031)
        assert descriptor['type'] == '0x20000003'
        assert image.u32(0x9ef0) == 0x940122 and image.u32(0x9f00) == 0x940123
        result = {'scope': __doc__, 'im_sha256': IM[1], 'descriptor': descriptor,
                  'cases': verify(image, obj), 'type_filter_and_missing_symbol_cases': 6,
                  'suspend_resume_cases': 2,
                  'original_sender_cases': 6, 'libObj_sha256': IMAGES['obj'][1],
                  'completion_messages': {'inact': '0x940122', 'act': '0x940123'},
                  'limits': ['No OSAL queue execution, GPU, camera access or physical sleep test.']}
        with a.output.open('x') as f:
            json.dump(result, f, indent=2)
            f.write('\n')
        print('IM lifecycle: 20 instruction-level cases passed; return value does not acknowledge act/inact.')
    finally:
        image.stream.close()
        database.stream.close()
        obj.stream.close()


if __name__ == '__main__':
    main()

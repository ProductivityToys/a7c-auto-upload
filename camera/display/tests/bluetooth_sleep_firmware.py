#!/usr/bin/env python3
"""Offline replay of the 2.00 Bluetooth receive/error path from the crash.

Runs original Thumb instructions; UART, logging and OSAL are explicit stubs.
This establishes possible causes of -4, not which UART event happened live.
No device access, binary patching, or change to Bluetooth settings.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image

CORE_SHA = "367eb2a29689dd8caf5109c60b9dbdcee29cc63fe45bd59f56f17b1582162bb2"


class Machine:
    OBJ, MSG, STOP, STACK = 0x300000, 0x301004, 0x302000, 0x40f000

    def __init__(self, image, selected, reads, policy_reply=0):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        pages = set()
        for segment in image.loads:
            start, length = segment['p_vaddr'], segment['p_memsz']
            pages.update(range(start & ~4095, (start + length + 4095) & ~4095, 4096))
        for page in sorted(pages):
            self.uc.mem_map(page, 4096)
        for segment in image.loads:
            self.uc.mem_write(segment['p_vaddr'], segment.data())
        # ELF virtual offset zero contains headers, but the camera loads the
        # DSO at 0x0cb93000. Keep absolute NULL unmapped in this offset replay.
        self.uc.mem_unmap(0, 4096)
        self.uc.mem_map(self.OBJ, 0x10000)
        self.uc.mem_map(0x400000, 0x10000)
        self.write(self.OBJ, 7)  # synthetic UART fd
        self.selected, self.reads, self.policy_reply = selected, list(reads), policy_reply
        self.events, self.fault, self.receive_result = [], None, None
        self.uc.hook_add(UC_HOOK_CODE, self.hook)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self.invalid)

    def write(self, address, value):
        self.uc.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def word(self, address):
        return struct.unpack('<I', self.uc.mem_read(address, 4))[0]

    def reg(self, register):
        return self.uc.reg_read(register)

    def ret(self, value=0):
        self.uc.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
        self.uc.reg_write(UC_ARM_REG_PC, self.reg(UC_ARM_REG_LR))

    def hook(self, uc, address, size, data):
        if address == self.STOP:
            uc.emu_stop()
        elif address in (0x923c, 0x97d4, 0x89d0, 0x8c20, 0x84fc):
            self.ret()  # BTBlog sink only
        elif address == 0x8768:
            # HCI send boundary: model command header needed by native checker.
            self.uc.mem_write(self.OBJ + 0x107, b'\x01\x10')
            self.ret()
        elif address in (0x9420, 0x879c):
            uc.reg_write(UC_ARM_REG_PC, (0x9e4c if address == 0x9420 else 0x9fe0) | 1)
        elif address == 0xa716:
            self.receive_result = struct.unpack('<i', struct.pack('<I', self.reg(UC_ARM_REG_R0)))[0]
        elif address == 0x9068:
            assert self.reg(UC_ARM_REG_R0) == 8
            timeval = self.word(self.reg(UC_ARM_REG_SP))
            self.events.append({'select': self.selected, 'timeout': [self.word(timeval), self.word(timeval + 4)]})
            self.ret(self.selected)
        elif address == 0x8b08:
            assert self.reads, 'Unexpected extra UART read'
            result = self.reads.pop(0)
            requested = self.reg(UC_ARM_REG_R2)
            if isinstance(result, bytes):
                assert len(result) <= requested
                self.uc.mem_write(self.reg(UC_ARM_REG_R1), result)
                result = len(result)
            self.events.append({'read': result, 'requested': requested})
            self.ret(result)
        elif address == 0x8d30:
            assert self.reg(UC_ARM_REG_R0) == 0x8f0139
            assert self.reg(UC_ARM_REG_R2) == 4 and self.reg(UC_ARM_REG_R3) == 1
            self.write(self.reg(UC_ARM_REG_R1), self.MSG)
            self.ret()
        elif address == 0x98f4:
            assert self.reg(UC_ARM_REG_R0) == 0x8f0139
            assert self.reg(UC_ARM_REG_R1) == self.MSG
            assert self.word(self.MSG - 4) == 0x8f0139
            assert bytes(self.uc.mem_read(self.MSG, 3)) == b'\x0e\x00\x00'
            self.events.append({'policy_reply': self.policy_reply, 'queue': '0x8f0139'})
            self.uc.mem_write(self.MSG + 2, bytes([self.policy_reply]))
            self.ret()
        elif address == 0x999c:
            self.ret()  # OSAL free boundary

    def invalid(self, uc, access, address, size, value, data):
        self.fault = {'access': access, 'address': address, 'size': size, 'pc': hex(self.reg(UC_ARM_REG_PC))}
        return False

    def run(self):
        self.uc.reg_write(UC_ARM_REG_SP, self.STACK)
        self.uc.reg_write(UC_ARM_REG_LR, self.STOP | 1)
        self.uc.reg_write(UC_ARM_REG_R0, self.OBJ)
        try:
            self.uc.emu_start(0xa6e1, self.STOP, count=20000)
        except UcError:
            if not self.fault:
                raise
        if not self.fault:
            assert self.reg(UC_ARM_REG_PC) == self.STOP, 'Instruction budget exhausted'
        return {'receive_result': self.receive_result, 'fault': self.fault, 'events': self.events,
                'result': None if self.fault else struct.unpack('<i', struct.pack('<I', self.reg(UC_ARM_REG_R0)))[0]}


def verify(image):
    cases = [
        ('select_timeout', 0, [], 0, -4, True, None),
        ('uart_eof', 1, [b''], 0, -4, True, None),
        ('uart_read_error', 1, [-1], 0, -4, True, None),
        ('one_byte_header', 1, [b'\x04'], 0, -4, True, None),
        ('two_byte_header', 1, [b'\x04\x0e'], 0, -4, True, None),
        ('policy_reply_nonzero', 0, [], 1, -4, False, -4),
        ('select_error', -1, [], 0, -1, False, -1),
        ('complete_reply', 1, [b'\x04\x0e\x04', b'\x01\x01\x10\x00'], 0, 7, False, 0),
    ]
    results = []
    for name, selected, reads, reply, receive, fault, result in cases:
        observed = Machine(image, selected, reads, reply).run()
        assert observed['receive_result'] == receive, (name, observed)
        assert bool(observed['fault']) == fault, (name, observed)
        assert observed['result'] == result, (name, observed)
        if fault:
            assert observed['fault'] == {'access': 20, 'address': 0, 'size': 1, 'pc': '0xa76c'}
        results.append({'case': name, **observed})
    return {'scope': 'Original HCI/receive/check/error instructions; UART, OSAL and log boundaries mocked. No live causality claim.',
            'core_sha256': CORE_SHA, 'cases': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(Image(args.core, CORE_SHA))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f"PASS {len(result['cases'])} original Bluetooth receive/error cases")

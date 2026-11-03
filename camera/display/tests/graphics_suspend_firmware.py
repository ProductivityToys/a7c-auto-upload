#!/usr/bin/env python3
"""Replay pinned 2.00 graphics suspend paths offline, with OS boundaries mocked.

Checks native dispatch/return handling and DDS send-before-join ordering.
Optional driver replay executes its ioctl switch with kernel services and
clock MMIO mocked. It does not execute a GPU or live IM phase scheduling.
No camera access and no additional runtime waits or hooks.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from elftools.elf.elffile import ELFFile
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image, IMAGES
from audit_frame_callback import branch
from audit_overlay_routes import expect


def audit(image):
    edges = {
        0x62cd42: 0x61e4ac, 0x62cd4e: 0x616550,
        0x61655e: 0x7f28c0,
        0x68edfc: 0x68c868, 0x68ee18: 0x68c868,
        0x68ee36: 0x785430, 0x68ee42: 0x75cb4e,
        0x785468: 0x784a50, 0x7ab506: 0x7d0bb0,
        0x7d0bc4: 0x77d950, 0x77d954: 0x77ef90,
        0x77ef98: 0x77e240, 0x7db66c: 0x7db184,
        0x68c898: 0x68c81e, 0x68c830: 0x68bec4,
    }
    for at, target in edges.items():
        assert branch(image, at) == target, hex(at)
    got = 0x784a58 + image.u32(0x784a80) + image.u32(0x784a84)
    table = image.u32(got)
    assert table == 0x13e6838
    assert image.u32(table + 0x5c) == image.u32(table + 0x28) == 0x7ab501
    expect(image, 0x77e25c, bytes.fromhex('48f208213a1dccf20401'))
    expect(image, 0x7db210, bytes.fromhex('686832f5aee3'))
    return {'branches': {hex(k): hex(v) for k, v in edges.items()},
            'backend_table': hex(table), 'suspend_ioctl': '0xc0048208',
            'dds_queue': '0x5c011d', 'dds_stop_operation': '0xff01',
            'dds_join': 'osal_wait_thread_exit',
            'limits': ['No GPU or kernel-driver execution.',
                       'Separate IM phase messages do not alone establish live phase order.',
                       'Native drain existence does not establish overlay/crash causality.']}


class Machine:
    OBJ, MSG, STOP, STACK = 0x3000000, 0x3001004, 0x3002000, 0x301f000

    def __init__(self, image):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for seg in image.loads:
            start = seg['p_vaddr'] & ~4095
            end = (seg['p_vaddr'] + seg['p_memsz'] + 4095) & ~4095
            self.uc.mem_map(start, end - start)
            self.uc.mem_write(seg['p_vaddr'], seg.data())
        self.uc.mem_map(self.OBJ, 0x20000)
        self.events = []
        self.ioctl_rc, self.hardware_result = 0, 1
        self.alloc_rc = self.send_rc = self.wait_rc = 0
        self.condition_wakes = 0
        self.write(0x13e6028, 7)  # synthetic graphics fd
        self.write(self.OBJ + 4, 42)  # synthetic DDS thread
        # Error print callback is not relevant to hardware result handling.
        error_got = 0x77e258 + image.u32(0x77e28c) + image.u32(0x77e290)
        self.write(error_got, self.OBJ + 0x100)
        self.write(self.OBJ + 0x100, self.STOP + 0x101)
        self.uc.hook_add(UC_HOOK_CODE, self.hook)

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
        elif address == 0x10f460:
            assert self.reg(UC_ARM_REG_R0) == 7
            assert self.reg(UC_ARM_REG_R1) == 0xc0048208
            self.events.append('hardware_suspend_ioctl')
            self.write(self.reg(UC_ARM_REG_R2), self.hardware_result)
            self.ret(self.ioctl_rc)
        elif address in (0x7db060, self.STOP + 0x100):
            self.ret()  # logging only
        elif address == 0x7dbf1c:
            self.events.append('dds_lock'); self.ret()
        elif address == 0x10dc98:
            assert self.reg(UC_ARM_REG_R0) == 0x5c011d
            assert self.reg(UC_ARM_REG_R2) == 12
            self.events.append('allocate_stop')
            self.write(self.reg(UC_ARM_REG_R1), self.MSG)
            self.ret(self.alloc_rc)
        elif address == 0x10f3b8:
            assert self.word(self.MSG - 4) == 0x5c011d
            assert bytes(uc.mem_read(self.MSG, 2)) == b'\x01\xff'
            self.events.append('send_stop'); self.ret(self.send_rc)
        elif address == 0x10d970:
            assert self.reg(UC_ARM_REG_R0) == 42
            self.events.append('join_dds_thread'); self.ret(self.wait_rc)
        elif address == 0x10ea54:
            self.events.append('free_stop'); self.ret()
        elif address == 0x68bec4:
            assert self.reg(UC_ARM_REG_R0) == self.OBJ + 8
            self.condition_wakes += 1
            # First wake is spurious; second changes the phase to ready.
            if self.condition_wakes == 2:
                self.write(self.OBJ + 4, 1)
            self.ret()

    def run(self, address, arg=0):
        self.uc.reg_write(UC_ARM_REG_SP, self.STACK)
        self.uc.reg_write(UC_ARM_REG_LR, self.STOP | 1)
        self.uc.reg_write(UC_ARM_REG_R0, arg)
        self.uc.emu_start(address | 1, self.STOP, count=10000)
        assert self.reg(UC_ARM_REG_PC) == self.STOP, 'Instruction budget exhausted'
        return self.reg(UC_ARM_REG_R0)


def verify(image):
    cases = []
    for fallback, ioctl_rc, result, expected in (
            (False, 0, 1, 1), (True, 0, 1, 1),
            (False, 0, 0, 0), (False, -1, 1, 0)):
        m = Machine(image)
        m.ioctl_rc, m.hardware_result = ioctl_rc, result
        if fallback:
            m.write(0x13e6838 + 0x5c, 0)
        assert m.run(0x784a50) == expected
        assert m.events == ['hardware_suspend_ioctl']
        cases.append({'path': 'graphics_suspend', 'fallback': fallback,
                      'ioctl_rc': ioctl_rc, 'hardware_result': result, 'result': expected})
    for alloc, send, wait, expected in (
            (0, 0, 0, ['dds_lock', 'allocate_stop', 'send_stop', 'join_dds_thread']),
            (-7, 0, 0, ['dds_lock', 'allocate_stop']),
            (0, -8, 0, ['dds_lock', 'allocate_stop', 'send_stop', 'free_stop']),
            (0, 0, -9, ['dds_lock', 'allocate_stop', 'send_stop', 'join_dds_thread'])):
        m = Machine(image)
        m.alloc_rc, m.send_rc, m.wait_rc = alloc, send, wait
        m.run(0x7db184, m.OBJ)
        assert m.events == expected
        cases.append({'path': 'dds_suspend', 'allocate_rc': alloc, 'send_rc': send,
                      'join_rc': wait, 'events': m.events})
    m = Machine(image)
    m.write(m.OBJ + 4, 0)
    assert m.run(0x68c81e, m.OBJ) == 1
    assert m.condition_wakes == 2 and m.word(m.OBJ + 4) == 2
    cases.append({'path': 'grm_phase_gate', 'spurious_wake_rechecked': True})
    return cases


def verify_driver(path):
    """Actual ioctl switch/state instructions, mocked locks/usercopy/clock MMIO."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == '2c8ed81ad14a596f28267bd7a017117ba60ea067dae788092c1ece8468b55fb3'
    with path.open('rb') as f:
        elf = ELFFile(f)
        code = elf.get_section_by_name('.text').data()
        rels = elf.get_section_by_name('.rel.text')
        symbols = elf.get_section(rels['sh_link'])
        imports = {r['r_offset']: symbols.get_symbol(r['r_info_sym']).name
                   for r in rels.iter_relocations() if r['r_info_type'] == 28}
    clock_calls = {a: name for a, name in imports.items() if 0x1a8 <= a < 0x230}
    assert len(clock_calls) == 10
    assert set(clock_calls.values()) == {'sugilite_ioread32', 'sugilite_iowrite32'}
    # Direct ARM BL: ioctl suspend -> clock wrapper -> clock-down function.
    for a, expected in ((0xe3c, 0x760), (0x76c, 0x1a8)):
        insn = struct.unpack_from('<I', code, a)[0]
        assert insn >> 24 == 0xeb
        offset = insn & 0xffffff
        if offset & 0x800000:
            offset -= 1 << 24
        assert a + 8 + offset * 4 == expected
    results = []
    base, file, device, arg, stack, stop = 0x100000, 0x3000000, 0x3001000, 0x3002000, 0x301f000, 0x3003000
    for operation, initial, final, result, action in (
            (0xc0048208, 0, 1, 1, ['clock_down']),
            (0xc0048208, 1, 1, 0, []),
            (0xc0048209, 1, 0, 1, ['clock_up', 'register_init']),
            (0xc0048209, 0, 0, 0, [])):
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.mem_map(base, 0x10000); u.mem_write(base, code)
        u.mem_map(file, 0x20000)
        def write(a, v): u.mem_write(a, struct.pack('<I', v))
        def word(a): return struct.unpack('<I', u.mem_read(a, 4))[0]
        write(file + 0xa8, device); write(device + 0x48, initial)
        write((stack & ~8191) + 8, 0x7fffffff)  # mocked thread address limit
        events = []
        def hook(uc, address, size, data):
            off = address - base
            if address == stop:
                uc.emu_stop()
            elif off in (0x760, 0x774, 0x54):
                events.append({0x760:'clock_down', 0x774:'clock_up', 0x54:'register_init'}[off])
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            elif off in imports:
                name = imports[off]
                if name == '__put_user_4':
                    assert uc.reg_read(UC_ARM_REG_R0) == arg
                    write(arg, uc.reg_read(UC_ARM_REG_R2))
                else:
                    assert name in ('__migrate_disable', '__migrate_enable', 'rt_spin_lock', 'rt_spin_unlock'), name
                uc.reg_write(UC_ARM_REG_R0, 0)
                uc.reg_write(UC_ARM_REG_PC, address + 4)  # intercept CALL site
        u.hook_add(UC_HOOK_CODE, hook)
        for reg, value in ((UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,stop),
                           (UC_ARM_REG_R0,file),(UC_ARM_REG_R1,operation),(UC_ARM_REG_R2,arg)):
            u.reg_write(reg, value)
        u.emu_start(base + 0x900, stop, count=1000)
        assert u.reg_read(UC_ARM_REG_PC) == stop and u.reg_read(UC_ARM_REG_R0) == 0
        assert word(device + 0x48) == final and word(arg) == result and events == action
        results.append({'ioctl': hex(operation), 'initial_state':initial,
                        'final_state':final, 'user_result':result, 'events':events})
    return {'sha256':digest, 'cases':results,
            'clock_down_imports':{hex(a):name for a,name in clock_calls.items()},
            'scope':'Actual ioctl switch; locks, usercopy, clock MMIO and register init mocked. Clock-down body statically checked; no hardware execution.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--driver', type=Path, help='Optional pinned camera 2.00 grm_gles.ko')
    a = p.parse_args()
    im = Image(a.research / IMAGES['obj'][0], IMAGES['obj'][1])
    try:
        result = {'firmware_sha256': IMAGES['obj'][1], 'camera_access': False,
                  'audit': audit(im), 'cases': verify(im)}
    finally:
        im.stream.close()
    if a.driver:
        result['driver'] = verify_driver(a.driver)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    count = len(result['cases']) + len(result.get('driver', {}).get('cases', []))
    print(f"Passed {count} offline cases: {a.output}")

#!/usr/bin/env python3
"""Replay 2.00 power receiver boundaries offline; no camera access.

Runs actual Thumb registration, LIRO off/completion and application event
translation. OSAL, allocation, logging and event delivery are replaced.
Does not emulate LIRO task teardown, application actions or GPU completion.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image, IMAGES
from audit_frame_callback import branch

AVCAM = "evidence/camera-avcam-20261029-105036/av-cam.bin"
AVCAM_SHA = "0113bf72420bd0b715821dada13a9cba058e78f2b5d68781dcb298317524d0f9"
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)

class Machine:
    BASE, STOP, STACK = 0x3000000, 0x300f000, 0x301f000

    def __init__(self, image=None, raw=None):
        self.u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        if image:
            for seg in image.loads:
                lo = seg['p_vaddr'] & ~4095
                hi = (seg['p_vaddr'] + seg['p_memsz'] + 4095) & ~4095
                self.u.mem_map(lo, hi-lo)
                self.u.mem_write(seg['p_vaddr'], seg.data())
        else:
            self.u.mem_map(0, (len(raw)+4095) & ~4095)
            self.u.mem_write(0, raw)
        self.u.mem_map(self.BASE, 0x20000)
        self.events, self.hooks = [], {}
        self.u.hook_add(UC_HOOK_CODE, self.hook)

    def word(self, a):
        return struct.unpack('<I', self.u.mem_read(a, 4))[0]

    def write(self, a, value):
        self.u.mem_write(a, struct.pack('<I', value & 0xffffffff))

    def hook(self, u, a, size, _):
        if a == self.STOP:
            u.emu_stop()
        elif a in self.hooks:
            value = self.hooks[a](*[u.reg_read(r) for r in REGS])
            u.reg_write(UC_ARM_REG_R0, (value or 0) & 0xffffffff)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def run(self, address, *args):
        self.events = []
        for r, v in zip(REGS, args):
            self.u.reg_write(r, v)
        self.u.reg_write(UC_ARM_REG_SP, self.STACK)
        self.u.reg_write(UC_ARM_REG_LR, self.STOP | 1)
        self.u.emu_start(address | 1, self.STOP, count=3000)
        assert self.u.reg_read(UC_ARM_REG_PC) == self.STOP
        return self.events.copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = (args.research / AVCAM).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == AVCAM_SHA
    path, sha = IMAGES['obj']
    image = Image(args.research / path, sha)
    cases = []

    m = Machine(raw=raw)
    word = lambda a: struct.unpack_from('<I', raw, a)[0]
    state = 0x5f3e6 + word(0x5f440)
    assert (0x5f3fe + word(0x5f448)) & 0xffffffff == 0x5f315
    m.hooks[0x6adf74] = lambda *r: 0  # logging
    def register(q, handle, cb, arg):
        assert (q, cb, arg) == (0x920195, 0x5f315, 0)
        m.write(handle, 7)
        m.events.append(['register', q, cb])
    def send(op, p1, source, header):
        m.events.append(['message', op, p1, source, header])
    m.hooks[0x1c9bc] = register
    m.hooks[0x5f33c] = send  # message construction independently decoded
    m.hooks[0x1c9a0] = lambda q, h, *_: m.events.append(['unregister', q, h])
    m.hooks[0x1c248] = lambda ident, *_: m.events.append(['osal_slot_0x34', ident])
    events = m.run(0x5f3dc)
    assert events == [['register', 0x920195, 0x5f315],
                      ['message', 0x92016e, 0x920195, 0, 0x920021]]
    cases.append({'case': 'LIRO register', 'events': events})
    for op, expected in ((0x920143, [['osal_slot_0x34', 8]]), (0x920145, [])):
        m.write(m.BASE, op)
        events = m.run(0x5f314, m.BASE)
        assert events == expected
        cases.append({'case': 'LIRO callback', 'operation': hex(op), 'events': events})
    events = m.run(0x5f384)
    assert events == [['message', 0x920144, 1, 0x920195, 0x920195],
                      ['unregister', 0x920195, 7]]
    assert m.word(state) == m.word(state+4) == 0
    cases.append({'case': 'LIRO completion and unregister', 'events': events})
    assert m.run(0x5f384) == []
    cases.append({'case': 'LIRO repeated completion sends nothing'})

    # Two distinct app queue registrations exist. Do not infer live selection.
    assert image.u32(0x3917a0) == 0x391551
    got = 0x697ea8 + image.u32(0x697f14)
    assert image.u32(got + image.u32(0x697f20)) == 0x697ca5
    assert branch(image, 0x6e1d50) == 0x3916f4
    assert image.u32(0x13b2718) == 0x6e1c75
    rtti = image.u32(0x13b26e4)
    name = image.u32(rtti+4)
    assert image.read(name, 10) == b'9ModelRoot'

    m = Machine(image=image)
    m.hooks[0x391410] = lambda *r: 0  # log wrapper
    m.hooks[0x108f50] = lambda *r: 0  # printf wrapper
    m.hooks[0x108f4c] = lambda *r: 0
    def new_event(event, mode, *_):
        assert mode == 2
        m.events.append(['new_event', event])
        return m.BASE+0x100
    def copy(dst, src, size, *_):
        assert size == 16
        m.u.mem_write(dst, bytes(m.u.mem_read(src, size)))
        return dst
    m.hooks[0x3ff4e0] = new_event
    m.hooks[0x1084d4] = lambda size, *_: m.BASE+0x200
    m.hooks[0x35403c] = copy
    m.hooks[0x109668] = lambda obj, key, payload, *_: m.events.append(
        ['attach_payload', key, [m.word(payload+i) for i in range(0, 16, 4)]])
    m.hooks[0x3ff4bc] = lambda *_: m.events.append(['dispatch_event'])
    for op, event in ((0x920143, 0x16030003), (0x920147, 0x16030009),
                      (0x920145, 0x16030004), (0x92015a, 0x16030002),
                      (0x920149, 0x16030005), (0x920148, 0x16030006)):
        words = [op, 11, 22, 33]
        for n, v in enumerate(words):
            m.write(m.BASE+n*4, v)
        events = m.run(0x391550, m.BASE)
        assert events == [['new_event', event], ['attach_payload', 0x16030001, words],
                          ['dispatch_event']]
        cases.append({'case': 'ModelRoot event bridge', 'operation': hex(op), 'events': events})
    assert branch(image, 0x6e2d4a) == 0x3918fc
    assert branch(image, 0x6e35f4) == 0x34d5a4
    assert image.u32(0x6e3610) == 0x16060009
    m.hooks[0x41f398] = lambda *r: 0  # action logging
    def send_app(op, p1, source, p3):
        header = m.word(m.u.reg_read(UC_ARM_REG_SP))
        m.events.append(['power_reply', op, p1, source, p3, header])
    m.hooks[0x391348] = send_app
    for queue in (0x920168, 0):
        m.write(0x1452460, queue)
        events = m.run(0x6e2d34, m.BASE+0x1000)
        expected = [['power_reply', 0x920144, 1, queue, 0, queue]] if queue else []
        assert events == expected
        cases.append({'case': 'ModelRoot power-off acknowledgement',
                      'registered_queue': hex(queue), 'events': events})
    result = {'firmware': 'ILCE-7C 2.00', 'camera_access': False,
              'sha256': {'avcam': AVCAM_SHA, 'libObj': sha}, 'cases': cases,
              'limits': ['OS boundaries and event delivery mocked.',
                         'LIRO task 8 semantics are not asserted.',
                         'Live application callback selection and GPU completion not tested.']}
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(f'Passed {len(cases)} offline cases: {args.output}')

if __name__ == '__main__':
    main()

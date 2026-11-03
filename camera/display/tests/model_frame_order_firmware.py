#!/usr/bin/env python3
"""Offline 2.00 model completion versus frame submission ordering.

Runs actual model FSM and frame control flow. Explicitly replaces application
selectors, event storage, time and render/GPU boundaries; no camera access.
"""
import argparse
import json
import sys
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R4, UC_ARM_REG_R7, UC_ARM_REG_PC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image, IMAGES
from power_receivers_firmware import Machine


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    path, sha = IMAGES['obj']
    image = Image(args.research / path, sha)
    cases = []
    # Pin the actual ModelBase vtable rather than guessing a +0x18 handler.
    vt = 0x13a2120
    assert image.read(image.u32(image.u32(vt+4)+4), 10) == b'9ModelBase'
    assert [image.u32(vt+8+o) for o in (8, 0x18)] == [0x41f71d, 0x41f645]

    for ident, expected in ((0x11004016, 0x11004017),
                            (0x1100400c, 0x1100400d),
                            (0x11004014, 0x11004015)):
        m = Machine(image=image)
        obj, event = m.BASE+0x100, m.BASE+0x400
        m.write(obj, vt+8)
        m.write(obj+0x1c, 4)  # Ordinary model, not the special ID -1 branch.
        m.write(obj+0x60, 0x11004001)
        cursor = [m.BASE+0x600]
        def alloc(size, *_):
            result = cursor[0]
            cursor[0] += 0x40
            return result
        def constructor(ptr, eid, dest, flags):
            m.write(ptr, eid)
            m.write(ptr+4, dest)
        def push(_, msg, *__):
            m.events.append(['enqueue', hex(m.word(msg)), m.word(msg+4)])
        def select(*_):
            m.events.append(['selector_no_transition'])
            return 0
        m.hooks.update({0x41ec74: select, 0x107e64: lambda *r: ident,
                        0x1084d4: alloc, 0x107998: constructor,
                        0x3520d4: lambda *r: 17,
                        0x34a1fc: lambda *r: 0,
                        0x109668: lambda *r: 0,
                        0x10caf8: push, 0x10cafc: push})
        events = m.run(0x89ab38, obj, event)
        assert events == [['selector_no_transition'],
                          ['enqueue', '0x11004001', 4],
                          ['enqueue', hex(expected), 2]]
        assert m.word(obj+8) == 14 and m.word(obj+0x14) == 0
        cases.append({'case': 'unhandled_model_lifecycle_default_completion',
                      'event': hex(ident), 'events': events})

    # Bounded slice of the real event loop: process one event, exhaust queue,
    # apply time gate, optionally draw, then record the native exit label.
    for draw_due in (False, True):
        m = Machine(image=image)
        obj, scratch, graphics = m.BASE+0x100, m.BASE+0x1000, m.BASE+0x500
        m.write(obj+8, graphics)
        m.write(scratch+0x18, 100)
        m.u.reg_write(UC_ARM_REG_R4, obj)
        m.u.reg_write(UC_ARM_REG_R7, scratch)
        m.hooks[0x899eac] = lambda *r: m.BASE+0x400
        m.hooks[0x89b5b4] = lambda *r: m.events.append(['dispatch_event'])
        for at in (0x89b540, 0x89d648, 0x89d488, 0x10aaa8):
            m.hooks[at] = lambda *r: 0
        def trace(index, label, *_):
            assert index == 0
            m.events.append(['stage', bytes(m.u.mem_read(label, 16)).decode().strip()])
        m.hooks[0x898380] = trace
        def clock(_, ptr, *__):
            m.write(ptr, 0)
            m.write(ptr+4, 0)
        def elapsed(ptr, *_):
            m.write(ptr, 0)
            m.write(ptr+4, 200 if draw_due else 0)
        m.hooks[0x10d2b4] = clock
        m.hooks[0x897e48] = elapsed
        m.hooks[0x89f4ec] = lambda *r: m.events.append(['draw'])
        def stop(u, address, size, _):
            if address == 0x89bf3e:
                u.reg_write(UC_ARM_REG_PC, m.STOP)
                u.emu_stop()
        from unicorn import UC_HOOK_CODE
        m.u.hook_add(UC_HOOK_CODE, stop)
        events = m.run(0x89be1e)
        assert events == [['dispatch_event'], ['stage', 'draw in']] + ([['draw']] if draw_due else []) + [['stage', 'draw out']]
        cases.append({'case': 'event_loop_slice', 'draw_due': draw_due, 'events': events})

    # Execute the real frame entry with mocked renderer/present boundaries.
    for dirty in (False, True):
        m = Machine(image=image)
        obj = m.BASE+0x100
        m.u.mem_write(obj+0x232, b'\x01')
        for at in (0x66dc48, 0x671fa4, 0x7e0478, 0x617d80, 0x617e8c, 0x618230):
            m.hooks[at] = lambda *r: 0
        m.hooks[0x80441e] = lambda *r: int(dirty)
        m.hooks[0x10ddf0] = lambda *r: 0  # Use fixed full-frame rectangle branch.
        for at, label in ((0x61819c, 'scene'), (0x66dd24, 'post'),
                          (0x66de3c, 'gain_hook'), (0x66dc04, 'present'),
                          (0x80477e, 'frame_cleanup'), (0x66ddc4, 'idle_backend')):
            m.hooks[at] = lambda *r, label=label: m.events.append([label])
        events = m.run(0x61f140, obj)
        assert events == ([[name] for name in ('scene', 'post', 'gain_hook',
                                               'present', 'frame_cleanup')]
                          if dirty else [['idle_backend']])
        cases.append({'case': 'frame_submission_order', 'dirty': dirty, 'events': events})

    result = {'firmware': 'ILCE-7C 2.00', 'libObj_sha256': sha,
              'camera_access': False, 'cases': cases,
              'limits': ['Application selector explicitly returns no transition.',
                         'Event storage, time and GPU/renderer calls are mocks.',
                         'Event-loop test is a bounded instruction slice, not a whole thread.',
                         'draw out is emitted even when the time gate skips the entire frame call.',
                         'Proves call order, not asynchronous GPU completion or crash causality.']}
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(f'Passed {len(cases)} offline cases: {args.output}')


if __name__ == '__main__':
    main()

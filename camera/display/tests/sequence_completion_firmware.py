#!/usr/bin/env python3
"""Replay pinned Sony SequenceManager completion dispatch; no camera access.

List lookup/removal, sequence callbacks and locking are mocked. Tests actual
Thumb branches/order, not asynchronous hardware completion or crash causality.
"""
import argparse
import json
import sys
from pathlib import Path
from unicorn.arm_const import UC_ARM_REG_R0
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image, IMAGES
from power_receivers_firmware import Machine

FW = 'evidence/ui-framework-20261029-135957/libBizFw.so'
SHA = '79b1ca36f60f5b3accbdb2dc4ed8f90c9b26dfd876397937dc82aa56dc89ae55'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    fw = Image(a.research/FW, SHA)
    path, sha = IMAGES['obj']
    obj_image = Image(a.research/path, sha)
    # Address point, not the preceding Itanium vtable header.
    assert obj_image.u32(0x13c7ac8+0x20) == 0xdc4f7d
    assert obj_image.u32(0x13c7ac8+0x28) == 0xdc4885
    cases = []
    for found, result in ((False, 0), (True, 0), (True, 0x111), (True, 1)):
        m = Machine(image=fw)
        manager, sequence, vt, msg, context = [m.BASE+i for i in (0x100,0x200,0x300,0x400,0x500)]
        m.write(sequence, vt)
        m.write(manager+0x50, context)
        def lookup(ptr, ident, *_):
            assert (ptr, ident) == (manager+8, 17)
            m.events.append(['lookup', ident])
            return sequence if found else 0
        def remove(ptr, value, *_):
            assert (ptr, value) == (manager+8, sequence)
            m.events.append(['remove'])
        m.hooks[0x2c3e0], m.hooks[0x2c950] = lookup, remove
        slots = ((0x50,'lock'), (0x54,'unlock'), (0x20,'response'),
                 (0x28,'send_completion'), (0x40,'pre_finished'),
                 (0x2c,'finished'), (0x44,'post_finished'), (4,'destroy'))
        for n, (slot, label) in enumerate(slots):
            at = m.BASE+0x1000+16*n
            m.write(vt+slot, at|1)
            def callback(this, arg, *_, label=label):
                assert this == sequence
                if label == 'response':
                    assert arg == msg
                elif label == 'send_completion':
                    assert arg == context
                elif label in ('pre_finished', 'finished', 'post_finished'):
                    assert arg == result
                m.events.append([label])
                return result if label == 'response' else 0
            m.hooks[at] = callback
        events = m.run(0x2eb52, manager, 17, msg)
        expected = [['lookup', 17]]
        if found:
            expected += [[s] for s in ('lock','response','unlock')]
            if result:
                expected += [[s] for s in ('remove','lock','send_completion',
                    'pre_finished','finished','post_finished','unlock','destroy')]
        assert events == expected
        assert m.u.reg_read(UC_ARM_REG_R0) == (result if found else 0x101)
        cases.append({'found':found, 'sequence_result':hex(result), 'events':events})
    with a.output.open('x') as f:
        json.dump({'firmware':'ILCE-7C 2.00', 'sha256':{'libBizFw':SHA,'libObj':sha},
            'camera_access':False, 'cases':cases,
            'limits':['Callbacks/list operations/locks replaced explicitly.',
                      'A nonzero sequence result triggers completion; it is not by itself a hardware success code.',
                      'No asynchronous GPU or power ordering is asserted.']}, f, indent=2)
        f.write('\n')
    print(f'Passed {len(cases)} firmware cases: {a.output}')

if __name__ == '__main__':
    main()

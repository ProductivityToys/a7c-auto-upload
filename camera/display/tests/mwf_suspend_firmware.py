#!/usr/bin/env python3
"""Replay actual 2.00 suspend reply ordering, with message/OS boundaries mocked.

This checks framework bookkeeping, not the concrete UI callback, GPU drain,
or the cause of the observed Bluetooth failure. No camera access.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image, IMAGES
from power_receivers_firmware import Machine

MWF = 'evidence/camera-mwf-20261029-110715/libMWF.so'
SHA = '96007d162fa1cb5e73947650859c31e797547979635ed0d6f7ac9c6c1821b8e1'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    image = Image(args.research / MWF, SHA)
    cases = []
    for callback_rc in (0, -1):
        for send_rc in (0, -1):
            m = Machine(image=image)
            obj, vtable, nested, callback = [m.BASE+x for x in (0x100, 0x200, 0x300, 0x400)]
            m.write(obj, vtable)
            m.write(vtable+0x6c, callback | 1)
            messages, params = {}, {}
            m.hooks[0x1ded8] = lambda *r: 0x1009
            for at in (0x1c394, 0x1ce50, 0x1dd60, 0x1df5c, 0x1da84,
                       0x1bccc, 0x1d678, 0x1d420):
                m.hooks[at] = lambda *r: 0  # constructors, destructors, logging
            def ptr_param(dst, value, *_):
                params[dst] = value
            def set_msg(dst, category, command, *_):
                messages[dst] = {'category': category, 'command': command, 'params': {}}
            def get_param(msg, key, kind, *_):
                assert key == 0x1000 and kind == 0x29
                return nested
            def suspend(this, msg, *_):
                assert (this, msg) == (obj, nested)
                m.events.append(['callback', callback_rc])
                return callback_rc
            def struct_value(dst, src, size, flags):
                assert (size, flags) == (4, 0)
                params[dst] = m.word(src)
            def add_param(msg, key, value, *_):
                messages[msg]['params'][key] = params[value]
            def send(this, msg, *_):
                assert this == obj
                body = messages[msg]
                assert (body['category'], body['command']) == (0x3000, 0x100b)
                assert body['params'] == {0x100: obj, 0x1000: callback_rc & 0xffffffff,
                                          0x1001: obj}
                m.events.append(['send_completion', callback_rc, send_rc])
                return send_rc
            m.hooks.update({0x1c438: ptr_param, 0x1d45c: set_msg, 0x1cbdc: get_param,
                            callback: suspend, 0x1bf84: struct_value,
                            0x1d9e0: add_param, 0x1c55c: send})
            events = m.run(0x29204, obj, m.BASE+0x500)
            assert events == [['callback', callback_rc],
                              ['send_completion', callback_rc, send_rc]]
            cases.append({'case': 'callback_before_completion', 'events': events})

    path, obj_sha = IMAGES['obj']
    image = Image(args.research / path, obj_sha)
    # This particular dispatcher does not read the callback-result parameter.
    # It is not a claim that no earlier layer can validate/filter the message.
    for message, state, notification in ((0x100b, 8, 6), (0x100a, 4, 7)):
        m = Machine(image=image)
        obj = m.BASE+0x100
        m.write(obj+4, 7)
        m.hooks[0x10c824] = lambda *r: 0x3000
        m.hooks[0x10d294] = lambda *r: message
        m.hooks[0x3a0966] = lambda *r: 0
        m.hooks[0x3a0d94] = lambda this, event, *_: m.events.append(['notify', event])
        def unexpected_param(*r):
            raise AssertionError('dispatcher unexpectedly read a result parameter')
        m.hooks[0x10d4c0] = unexpected_param
        events = m.run(0x3a18f8, obj, m.BASE+0x500)
        assert m.word(obj+4) == state
        assert events == [['notify', notification]]
        cases.append({'case': 'object_reply_dispatch', 'message': hex(message),
                      'state': state, 'events': events})
    # ObjDisplay's actual sequence completion clears the wait byte only when
    # its owner pointer can be resolved. Execute the real byte setter too.
    assert image.u32(0x13c7ac8+0x28) == 0xdc4885
    rtti = image.u32(0x13c7ac8-4)
    name = image.read(image.u32(rtti+4), 80).split(b'\0')[0]
    assert name == b'N10OBJDISPLAY30SequenceCmnSuspendTerminateCmdE'
    for scenario in ('missing_context', 'missing_root', 'query_error', 'null_owner', 'valid'):
        m = Machine(image=image)
        seq, ctx, root, owner, vt1, vt2, getter, query = [
            m.BASE+x for x in (0x100, 0x200, 0x300, 0x400, 0x800, 0x900, 0xa00, 0xb00)]
        m.write(seq+0x14, 0 if scenario == 'missing_context' else ctx)
        m.write(ctx, vt1)
        m.write(root, vt2)
        m.write(vt1+0x3c, getter | 1)
        m.write(vt2+0x4c, query | 1)
        m.u.mem_write(owner+0x280, b'\x5a\x01\xa5')
        m.hooks[getter] = lambda *r: 0 if scenario == 'missing_root' else root
        m.hooks[0x10fa4c] = lambda *r: 0  # logging disabled
        def owner_query(this, key, dst, *_):
            assert (this, key) == (root, 0x102b)
            m.write(dst, 0 if scenario == 'null_owner' else owner)
            return -1 if scenario == 'query_error' else 0
        m.hooks[query] = owner_query
        m.run(0xdc4884, seq)
        actual = bytes(m.u.mem_read(owner+0x280, 3))
        assert actual == (b'\x5a\x00\xa5' if scenario == 'valid' else b'\x5a\x01\xa5')
        cases.append({'case': 'display_sequence_clear', 'scenario': scenario,
                      'wait_byte': actual[1]})
    result = {'firmware': 'ILCE-7C 2.00', 'libMWF_sha256': SHA,
              'libObj_sha256': obj_sha, 'camera_access': False, 'cases': cases,
              'limits': ['Concrete onSuspendingWithParam callback mocked.',
                         'Message constructors, parameter storage and delivery mocked.',
                         'Does not establish end-to-end failure handling or GPU completion.']}
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(f'Passed {len(cases)} offline cases: {args.output}')


if __name__ == '__main__':
    main()

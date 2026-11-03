#!/usr/bin/env python3
"""Offline 2.00 ModelRoot action ordering and topology suspend entry checks.

Actual Thumb selectors/dispatchers run; event getters, action bodies and
topology worker boundary are mocked. This is not a GPU completion test.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ui_contract import Image, IMAGES
from audit_frame_callback import branch
from power_receivers_firmware import Machine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path, sha = IMAGES['obj']
    image = Image(args.research / path, sha)
    cases = []
    m = Machine(image=image)
    for state, event, expected in (
        (0, 0x16030003, (2, 20)), (1, 0x16030003, (2, 20)),
        (2, 0x11004007, (3, -1)), (2, 0x1100400c, (3, 30)),
        (3, 0x16060002, (-1, 10)), (3, 0x16030009, (4, -1)),
        (3, 4, (-1, 36)), (4, 4, (-1, 14)),
        (0, 0x16060002, (-1, -1)), (4, 0x16060002, (-1, -1)),
    ):
        m.hooks[0x41ef76] = lambda *r, e=event: e
        m.hooks[0x364eec] = lambda *r, s=state: s
        m.hooks[0x6e25c8] = lambda *r: 1
        m.write(m.BASE+0x100, -1)
        m.write(m.BASE+0x104, -1)
        m.run(0x6e25f4, m.BASE+0x1000, m.BASE+0x100, m.BASE+0x104)
        result = [m.word(m.BASE+0x100), m.word(m.BASE+0x104)]
        assert result == [v & 0xffffffff for v in expected]
        cases.append({'case': 'selector', 'state': state, 'event': hex(event),
                      'new_state_and_action': result})

    for at, target in ((0x6e3e46, 0x6e2d34), (0x6e3f04, 0x6e2fd8),
                       (0x6e3f0e, 0x6e35b0), (0x34d5ac, 0x3819dc)):
        assert branch(image, at) == target
    for address, name in ((0x6e2d34, 'power_off_ok'),
                          (0x6e2fd8, 'input_invalid_ok'),
                          (0x6e35b0, 'suspend_topology')):
        m.hooks[address] = lambda *r, n=name: m.events.append(n)
    for action, expected in ((10, ['power_off_ok']),
                             (14, ['input_invalid_ok']),
                             (36, ['input_invalid_ok', 'suspend_topology'])):
        events = m.run(0x6e3d94, m.BASE+0x1000, action)
        assert events == expected
        cases.append({'case': 'action_order', 'action': action, 'events': events})

    # 0x16060009 is a ParamList key, not an event sent by this entry.
    m = Machine(image=image)
    obj = m.BASE+0x2000
    m.write(0x14516c4, obj)
    for at in (0x37c900, 0x37c928, 0x37c862, 0x108f50):
        m.hooks[at] = lambda *r: 0  # logs
    m.hooks[0x37cf20] = m.hooks[0x37ccfc] = lambda *r: 0
    m.hooks[0x38196c] = lambda mode, *_: m.events.append(['begin_suspend', mode])
    for state, parameter, expected in (
        (0, None, [['begin_suspend', 0]]),
        (4, 2, [['begin_suspend', 1]]),
        (3, 2, []), (1, 2, []),
    ):
        m.write(obj+0xc, state)
        m.write(obj+0xa8, 99)
        def lookup(params, key, *_):
            assert key == 0x16060009
            return m.BASE+0x3000 if parameter is not None else 0
        m.hooks[0x3520f2] = lookup
        m.hooks[0x3520ea] = lambda *r: parameter
        events = m.run(0x3819dc, m.BASE+0x1000)
        assert events == expected
        expected_parameter = (1 if parameter is None else parameter) if expected else 99
        assert m.word(obj+0xa8) == expected_parameter
        cases.append({'case': 'topology_entry', 'state': state,
                      'parameter': parameter, 'events': events})
    result = {'firmware': 'ILCE-7C 2.00', 'libObj_sha256': sha,
              'camera_access': False, 'cases': cases,
              'limits': ['Numeric states/events are not assigned lifecycle names without evidence.',
                         'Action bodies and topology worker boundary mocked.',
                         'Not an end-to-end UI/GPU shutdown or crash-causality test.']}
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(f'Passed {len(cases)} offline cases: {args.output}')


if __name__ == '__main__':
    main()

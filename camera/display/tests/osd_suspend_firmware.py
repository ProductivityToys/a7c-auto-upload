#!/usr/bin/env python3
"""Offline 2.00 OSD suspend, completion and interrupted-suspend paths.

Runs original Thumb control flow. Event allocation/delivery, logging and the
state setter boundary are mocked; no hardware, GPU or camera access.
"""
import argparse
import json
import sys
from pathlib import Path

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

    def setup(state, substate=0):
        m = Machine(image=image)
        obj, event = m.BASE+0x100, m.BASE+0x400
        m.write(obj+0xa4, state)
        m.write(obj+0xa8, substate)
        for at in (0x89b00c, 0x89b17c, 0x89b106):
            m.hooks[at] = lambda *r: 0
        m.hooks[0x1084d4] = lambda *r: event
        def make_event(dst, ident, dest, flags):
            assert dst == event and flags == 0
            m.write(dst, ident)
            m.write(dst+4, dest)
        def push(this, msg, *_):
            assert this == obj
            m.events.append(['enqueue', hex(m.word(msg)), m.word(msg+4)])
        def set_state(this, value, *_):
            assert this == obj
            m.events.append(['state', hex(value)])
            m.write(this+0xa4, value)
        m.hooks.update({0x107998: make_event, 0x10cafc: push, 0x8a09fc: set_state})
        return m, obj

    # Entry starts the actual suspend state machine only from two legal states.
    for state, accepted in ((0x30000, True), (0x70000, True), (0x60000, False)):
        m, obj = setup(state)
        m.hooks[0x8a1ed4] = lambda this, *_: m.events.append(['drive', hex(m.word(this+0xa8))])
        events = m.run(0x8a276c, obj)
        assert events == ([['state', '0x50000'], ['drive', '0x50000']] if accepted else [])
        cases.append({'case': 'suspend_entry', 'initial_state': hex(state), 'events': events})

    m, obj = setup(0x50000, 0x50002)
    events = m.run(0x8a1ed4, obj)
    assert events == [['enqueue', '0x11004010', 4], ['state', '0x60000']]
    assert m.word(obj+0xa8) == 0
    cases.append({'case': 'normal_terminal', 'events': events})

    # Execute the real per-model pending predicate, not a canned busy response.
    m, obj = setup(0x50000, 0x50101)
    node, model = m.BASE+0x500, m.BASE+0x600
    m.write(obj+0x20, node)
    m.write(model+8, 0x40000)
    m.write(model+12, 2)
    m.hooks[0x89b004] = lambda *r: 17
    m.hooks[0x8a10ba] = lambda *r: model
    assert m.run(0x8a1ed4, obj) == []
    assert (m.word(obj+0xa4), m.word(obj+0xa8)) == (0x50000, 0x50101)
    cases.append({'case': 'model_pending_no_completion', 'events': []})

    # Opposite lifecycle request can also issue the same terminal event while
    # moving directly into 0x70000. Thus that event alone is not a GPU fence.
    for state in (0x50000, 0x60000):
        m, obj = setup(state)
        m.hooks[0x8a1ed4] = lambda this, *_: m.events.append(['drive', hex(m.word(this+0xa8))])
        events = m.run(0x8a26d8, obj)
        expected = ([['enqueue', '0x11004010', 4]] if state == 0x50000 else [])
        expected += [['state', '0x70000'], ['drive', '0x70000']]
        assert events == expected
        cases.append({'case': 'opposite_request', 'initial_state': hex(state), 'events': events})

    # Actual routing distinguishes View (4), models (2) and graphics (1).
    # Recipient bodies are replaced: this checks routing, not their side effects.
    for dest, recipient in ((4, 'view'), (2, 'models'), (1, 'graphics')):
        m = Machine(image=image)
        dispatcher, event = m.BASE+0x100, m.BASE+0x400
        m.hooks[0x107e64] = lambda *r: 0x11004010
        m.hooks[0x109374] = lambda *r: dest
        for at in (0x898380, 0x10e454, 0x109ad8):
            m.hooks[at] = lambda *r: 0
        for at, label in ((0x89e758, 'view'), (0x8a28ac, 'models'),
                          (0x89f58c, 'graphics')):
            m.hooks[at] = lambda *r, label=label: m.events.append(['dispatch', label])
        events = m.run(0x89b5b4, dispatcher, event)
        assert events == [['dispatch', recipient]]
        assert m.word(dispatcher+0x48) == 0
        cases.append({'case': 'destination_routing', 'destination': dest, 'events': events})

    m = Machine(image=image)
    manager, queue, event = m.BASE+0x100, m.BASE+0x200, m.BASE+0x400
    m.write(manager, queue)
    def queue_push(this, msg, flag, *_):
        assert (this, msg, flag) == (queue, event, 1)
        m.events.append(['EventManager::push', flag])
    m.hooks[0x10b934] = queue_push
    events = m.run(0x8a02e8, manager, event)
    assert events == [['EventManager::push', 1]]
    cases.append({'case': 'completion_enqueue_boundary', 'events': events})

    result = {'firmware': 'ILCE-7C 2.00', 'libObj_sha256': sha,
              'camera_access': False, 'cases': cases,
              'limits': ['State setter, event creation/delivery and logging mocked.',
                         'Entry/terminal/pending/interruption and routing only; not all model transitions.',
                         'EventManager and destination handlers mocked; no queue concurrency simulated.',
                         'No inference of GPU completion or observed crash causality.']}
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(f'Passed {len(cases)} offline cases: {args.output}')


if __name__ == '__main__':
    main()

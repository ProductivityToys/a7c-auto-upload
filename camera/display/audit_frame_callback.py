#!/usr/bin/env python3
"""Offline ILCE-7C 2.00 post-draw route; no camera access or hook install."""
import argparse
import json
import struct
from pathlib import Path

from audit_ui_contract import Image, IMAGES
from audit_overlay_routes import expect


def branch(image, address):
    """Decode the Thumb-2 BL/B.W encodings used in the selected native path."""
    hi, lo = struct.unpack('<HH', image.read(address, 4))
    if hi & 0xf800 != 0xf000 or lo & 0xd000 not in (0x9000, 0xd000):
        raise ValueError(f'Expected Thumb BL/B.W at {address:x}')
    sign = (hi >> 10) & 1
    i1 = 1 ^ ((lo >> 13) & 1) ^ sign
    i2 = 1 ^ ((lo >> 11) & 1) ^ sign
    offset = sign << 24 | i1 << 23 | i2 << 22 | (hi & 1023) << 12 | (lo & 2047) << 1
    if sign:
        offset -= 1 << 25
    return address + 4 + offset


def audit(image):
    # View::drawDirect loads its ViewManager; the manager then loads an
    # internal object before selecting GraphicsEngine. Skipping +0x14 reads
    # a different object that can also contain plausible zero callback words.
    expect(image, 0x8989a0, bytes.fromhex('406abde88040'))
    expect(image, 0x89ce5c, bytes.fromhex('6069bde8b040'))
    expect(image, 0x89f56a, bytes.fromhex('2069bde8f041'))
    expect(image, 0x89f6c2, bytes.fromhex('636928469847'))
    expect(image, 0x350064, bytes.fromhex('80b500af406880bd'))
    expect(image, 0x3ef544, bytes.fromhex('b0b500af044618f58cec0d4b984215d1'))
    expect(image, 0x61805a, bytes.fromhex('80b500afc0f82c1280bd'))
    expect(image, 0x61806e, bytes.fromhex('80b500af80f8311280bd'))
    expect(image, 0x6180d6, bytes.fromhex('90f83132b0b5054600af9bb1d0f82c3283b1'))
    expect(image, 0x6180ec, bytes.fromhex('03680446db6a9847d5f82c329847236820461b6b984723682046db699847'))
    edges = {
        0x8989a6: 0x89ce50,  # View -> ViewManager draw
        0x89ce62: 0x89f4ec,  # ViewManager+0x14 -> internal draw
        0x89f570: 0x61f140,  # internal+0x10 -> GraphicsEngine frame
        0x89b6d4: 0x89f58c,  # event dispatch -> internal event handler
        0x89bede: 0x89f4ec,  # normal event loop -> internal draw
        0x6181b2: 0x618126,  # optional pre-draw callback
        0x6181e0: 0x7e049a,  # scene graph rendering
        0x6181fa: 0x6180d6,  # optional post-draw callback
        0x6180e8: 0x66dd9c,  # shared graphics context getter
        0x61f1ac: 0x61819c,  # native frame -> scene draw
        0x61f1c4: 0x66de3c,  # gain handling still follows callback
        0x61f1c8: 0x66dc04,  # native present/finish still follows callback
        0x7e6978: 0x78b730,  # delegate +168/+16c -> surface presentation
    }
    for source, target in edges.items():
        if branch(image, source) != target:
            raise ValueError(f'Native call edge changed: {source:x}')
    context = (image.u32(0x66dda8) + 0x66dda4) & 0xffffffff
    present_context = (image.u32(0x66dc44) + 0x66dc2c) & 0xffffffff
    if context != 0x1453918 or context != present_context:
        raise ValueError('Graphics context getter/present no longer share the same global')
    if image.u32(0x13b68c0 + 0x18) != 0x7ec7f1 or image.u32(0x13b6648 + 0x18) != 0x7e6935:
        raise ValueError('Presentation delegation changed')
    expect(image, 0x7e6970, bytes.fromhex('d4f86801d4f86c11'))
    expect(image, 0x7e697c, bytes.fromhex('094b7b441b681bb10848784400689847'))
    after_slot = (image.u32(0x7e69a4) + 0x7e6982) & 0xffffffff
    after_arg = (image.u32(0x7e69a8) + 0x7e698a) & 0xffffffff
    if (after_slot, after_arg) != (0x145abe4, 0x145abe8):
        raise ValueError('Trailing presentation callback globals changed')
    # DDS current front: singleton manager -> first inline entry -> bitmap.
    got = (image.u32(0x75898c) + 0x758950) & 0xffffffff
    manager_slot = (got + image.u32(0x758994)) & 0xffffffff
    if image.u32(manager_slot) != 0x1453df0:
        raise ValueError('DDS manager relocation addend changed')
    # Window+58 owns a resource selector; another +58 is its 8-byte vector.
    expect(image, 0x75b2fa, bytes.fromhex('4268036880b5d01a00afc01080bd'))
    expect(image, 0x75b3fe, bytes.fromhex('006880b500ebc10000af80bd'))
    if image.u32(0x13b3da0+0x20) != 0x75b50d or image.u32(0x13b3da0+0x1c) != 0x75b5a1:
        raise ValueError('Native window getters changed')
    for address in (0x78c7e0, 0x78c7f0):
        expect(image, address, bytes.fromhex('80b400afbd4680bc7047'))
    return {
        'scope': 'offline firmware facts; not a live callback or screen proof',
        'sha256': IMAGES['obj'][1], 'camera_access': False,
        'view_manager_global': hex(image.symbols['pViewManager']['st_value']),
        'view_manager_internal_offset': '0x14',
        'internal_engine_offset': '0x10',
        'engine_chain': '*pViewManager -> *(manager+0x14) -> *(internal+0x10)',
        'event_dispatch': {'internal_handler_offset': '0x14', 'dispatcher': '0x89f58c',
                           'default_call': '0x89f6c2: ldr r3,[r4,#0x14]; mov r0,r5; blx r3',
                           'identified_handler': '0x3ef544',
                           'handler_event_id': hex(image.u32(0x3ef584)),
                           'warning': 'single pointer load permits non-null restoration; it does not prove UI thread exclusivity or safe module unmapping'},
        'engine': {'pre_callback': '0x228', 'pre_enabled': '0x230',
                   'post_callback': '0x22c', 'post_enabled': '0x231',
                   'post_setter': '0x61805a', 'post_enable_setter': '0x61806e'},
        'post_callback_dispatch': '0x6180d6', 'context_global': hex(context),
        'post_sequence': ['context virtual +0x2c', 'engine callback +0x22c',
                          'context virtual +0x30', 'context virtual +0x1c'],
        'present_chain': ['0x66dc04', 'outer virtual +0x18: 0x7ec7f0',
                          'delegate virtual +0x18: 0x7e6934', '0x78b730'],
        'present_arguments': {'delegate_offsets': ['0x168', '0x16c'],
                              'meaning': 'display/surface handles, not proven pixel pointers'},
        'after_present': {'slot': hex(after_slot), 'argument': hex(after_arg),
                          'runs_even_if_boundary_returns_false': True},
        'window_front_lookup': {'dds_manager': '0x1453df0', 'dds_count': 'manager+0x58',
                                'dds_first_bitmap': 'manager+0x8c',
                                'window_vtable': '0x13b3da0', 'resource_vector': 'window+0xb0',
                                'current_index': 'window+0xbc', 'entry_bytes': 8,
                                'note': 'Offline structure; actual object equality requires runtime observation.'},
        'edges': {hex(s): hex(t) for s, t in edges.items()},
        'limits': ['Only dirty-scene path invokes this callback; it is not an independent refresh timer.',
                   'Native gain handling and present follow this callback; it is not after LCD presentation.',
                   'Setter has no synchronization; live installation and removal require separate lifetime handling.',
                   'Post-dispatch tests the callback then reloads it after context +0x2c: clearing the slot during dispatch can cause a null call.',
                   'Actual backend virtual methods, thread/lock context and existing callback owner require runtime inspection.',
                   'Calling native_submit from this callback is not yet established as safe.'],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    image = Image(args.research / IMAGES['obj'][0], IMAGES['obj'][1])
    try:
        result = audit(image)
    finally:
        image.stream.close()
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(args.output)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Offline fixed-firmware rectangle route; no camera writes or registration."""
import argparse
import json
from pathlib import Path
from audit_ui_contract import Image, IMAGES
from audit_overlay_routes import expect
from audit_frame_callback import branch, audit as audit_frame


def audit(image):
    frame = audit_frame(image)
    if image.u32(0x13af2f8 + 0x4c) != 0x631f21:
        raise ValueError('Sprite drawing virtual entry changed')
    for at, to in {0x631fe2: 0x6314a4, 0x632036: 0x6314a4,
                   0x631a9a: 0x672318, 0x672328: 0x671b6c,
                   0x67232c: 0x66dd9c, 0x67235a: 0x671b4c,
                   0x7ecfe4: 0x7e59b0,0x7e59ca:0x7e50b0,
                   0x7e59ec:0x7e5250,0x7e5a0e:0x7e4e24,
                   0x7e5afe:0x7e4ce4,0x7e4f46:0x7e4d9c}.items():
        if branch(image, at) != to:
            raise ValueError('Rectangle route changed at %x' % at)
    expect(image, 0x672336, bytes.fromhex('bc807b44fd803e81'))
    expect(image, 0x672340, bytes.fromhex('a7f80a80'))
    expect(image, 0x672354, bytes.fromhex('0368db6f9847'))
    # Explicit four color bytes and x/y/w/h halfwords reach context virtual+7c.
    for address, expected in [(0x13b68c0+0x7c,0x7ecf9d),
                              (0x13b6648+0x7c,0x7ebc87)]:
        if image.u32(address) != expected:
            raise ValueError('Rectangle backend virtual changed')
    expect(image, 0x7ecfa8, bytes.fromhex('90f80414904611f00101'))
    color = 0x67233c + image.u32(0x672368)
    if color != 0x1453967 or 0x67230e + image.u32(0x672314) != color:
        raise ValueError('Native shared color address changed')
    transforms = {0xa0:0x7ecdd3,0xa8:0x7ece09,0xc0:0x7ec3b1,
                  0xc8:0x7ed2a5,0xcc:0x7ed28b,0xd0:0x7ec32d,
                  0xd4:0x7efee3,0x120:0x7ed271}
    for offset,target in transforms.items():
        if image.u32(0x13b68c0+offset)!=target:
            raise ValueError('Native transform virtual changed')
    expect(image,0x7ec32c,bytes.fromhex('80b500afc0f8481380bd'))
    expect(image,0x7ed2a4,bytes.fromhex('d0f848335c22'))
    expect(image,0x7ed28a,bytes.fromhex('d0f848335c22'))
    for at,to in {0x7ed2ba:0x802a78,0x7ed2a0:0x80291c,
                  0x7ed286:0x8029f0,0x671c28:0x8069d8,
                  0x671c3a:0x8069d8}.items():
        if branch(image,at)!=to:raise ValueError('Transform stack route changed')
    if image.u32(0x13b68c0+0x1c)!=0x7ec7b9:
        raise ValueError('Post flush wrapper changed')
    expect(image,0x7ec7d8,bytes.fromhex('20690368db699847'))
    expect(image,0x7e5072,bytes.fromhex('2a682846d2f8e060626db047'))
    expect(image,0x7e5092,bytes.fromhex('0023a4f862300120'))
    if image.u32(0x13b6648+0xe0)!=0x7ebacd:
        raise ValueError('Indexed backend virtual changed')
    for at,to in {0x7ebade:0x7eb860,0x7eb872:0x7eb0ae,
                  0x7eb8b8:0x7eb0bc,0x7eb8dc:0x7eb63c,
                  0x7eb8fa:0x7eb770,0x7eb922:0x7eb0ca,
                  0x7eba34:0x7bc1e0,0x7eba48:0x7b81c0,
                  0x7eba4e:0x7bd040,0x7ebb38:0x7bd160}.items():
        if branch(image,at)!=to:raise ValueError('Indexed preparation route changed')
    expect(image,0x7eb894,bytes.fromhex('03681b6c9847'))
    expect(image,0x7eba38,bytes.fromhex('061e0bdb'))
    expect(image,0x7eba82,bytes.fromhex('01252846'))
    expect(image,0x7ebb3c,bytes.fromhex('0120'))
    if image.u32(0x13b6408+2*8)!=0x7e3875 or image.u32(0x13b6408+2*8+4):
        raise ValueError('Scissor state member mapping changed')
    expect(image,0x7e3884,bytes.fromhex('40f61140'))
    expect(image,0x7eaf24,bytes.fromhex('80b5603000af80bd'))
    if (image.u32(0x13b68c0+0x108),image.u32(0x13b68c0+0x10c))!=(0x7ec829,0x7ed151):
        raise ValueError('Native drawing scope changed')
    expect(image,0x7ec8a2,bytes.fromhex('23682046db6a9847'))
    expect(image,0x7ed1b2,bytes.fromhex('2b6828461b6b9847'))
    for offset,target in {0x48:0x7ec5bd,0x4c:0x7ec585,0x5c:0x7ec515}.items():
        if image.u32(0x13b68c0+offset)!=target:
            raise ValueError('Native viewport virtual changed')
    expect(image,0x7ec888,bytes.fromhex('23682046db6d9847'))
    expect(image,0x7ec89a,bytes.fromhex('2946966c2a46b047'))
    if branch(image,0x7ed182)!=0x7e4f18:
        raise ValueError('Drawing end queue submit changed')
    # This region is x0/y0/x1/y1 used by native gain's scissor, not a width/
    # height viewport update. The neutral-gain path returns without drawing.
    if (0x67555c+image.u32(0x6755ec))&0xffffffff != 0x674a51:
        raise ValueError('Region callback initialization changed')
    expect(image,0x675556,bytes.fromhex('254b7b446363'))
    region_globals=[(pc+image.u32(literal))&0xffffffff for pc,literal in
                    [(0x674a5a,0x674a70),(0x674a60,0x674a74),
                     (0x674a66,0x674a78),(0x674a6c,0x674a7c)]]
    if region_globals != [0x14539ae,0x14539ac,0x1453a4c,0x1453a4e]:
        raise ValueError('Region storage changed')
    expect(image,0x674a58,bytes.fromhex('2080064878440180054979440a80054a7a441380'))
    expect(image,0x675282,bytes.fromhex('1b78642b04d1404b7b441b78642b6dd0'))
    gain_globals=[(pc+image.u32(literal))&0xffffffff for pc,literal in
                  [(0x675282,0x675388),(0x67528e,0x67538c)]]
    if gain_globals != [0x13e5b61,0x13e5b62]:raise ValueError('Gain fields changed')
    for at,to in {0x61f1c0:0x66dd24,0x61f1c4:0x66de3c,0x61f1c8:0x66dc04,
                  0x6752d4:0x671da0,0x7e6978:0x78b730}.items():
        if branch(image,at)!=to:raise ValueError('Gain/presentation order changed')
    return dict(scope='offline route and ABI only; no live installation or LCD proof',
                firmware_sha256=IMAGES['obj'][1], camera_access=False,
                sprite_draw='0x631f20', rectangle='0x672318',
                color_global=hex(color), color_bytes=4, rectangle_halfwords=4,
                context_virtual='0x7c', outer='0x7ecf9c',
                active_flag='outer+0x404 bit0', primitive_dispatch='0x7e59b0',
                transform=dict(selector='outer+0x348',stack_offset='0x34c',stride='0x5c',
                               enter='0x671b6c',leave='0x671b4c',
                               push='0x802a78',pop='0x80291c',
                               selector_not_restored_by_leave=True,
                               shared_color_not_restored_by_rectangle=True,
                               dimensions=['0x1453978','0x1453964'],
                               local_color_candidate='module/native_rect_bar.h'),
                frame_order=frame['post_sequence'],
                gain_region=dict(setter='0x674a50',callback_slot='+0x34',
                                 coordinates='x0,y0,x1,y1',globals=list(map(hex,region_globals)),
                                 consumer='native gain scissor at 0x6752d4',
                                 neutral_gain_globals=list(map(hex,gain_globals)),
                                 neutral_gain_value=100,
                                 trial='Reject non-neutral gain; do not change dirty region or gain settings'),
                queue=dict(offset='outer+0x2c4',primitive_count='+0x62 halfword',
                           vertex_stride=64,vertices_per_rectangle=4,
                           five_rectangle_indices=28,submit='0x7e4f18',
                           native_post_flush_submits_cpu_batch=False,
                           final_draw='delegate virtual+0xe0',
                           final_draw_result_discarded=True,
                           candidate_submits_before_post_state_restore=True),
                indexed_backend=dict(entry='0x7ebacc',prepare='0x7eb860',
                    requirements=['shader binding +0x13c nonnull',
                        'shader virtual +0x40 succeeds','vertex binding +0x118 nonnull',
                        'layout binding +0x130 nonnull','texture preparation 0x7eb770 succeeds',
                        'index binding +0x124 nonnull'],
                    attribute_location='0x7bc1e0',missing_attribute_still_returns_success=True,
                    gpu_draw_boundary='0x7bd160',gpu_completion_checked=False,
                    fixture='tests/native_rect_backend.h',
                    fixture_scope='10 isolated ARM cases; actual preparation/dispatch, simulated texture/resources/GL'),
                drawing_scope=dict(begin='0x7ec828',end='0x7ed150',
                                   begin_also_pushes_graphics_state=True,
                                   end_also_pops_graphics_state=True,
                                   live_post_active_state_unmeasured=True,
                                   gain_scope_observer='module/gain_scope.h',
                                   begin_changes_viewport_outside_saved_state=True,
                                   owned_candidate_restores_viewport_after_end=True),
                scissor=dict(state_index=2,setter='0x7e3874',gl_cap='0x0c11',
                    cached_rectangle='delegate+0x60, halfwords x/y/w/h, GL bottom origin',
                    begin_does_not_disable_scissor=True,
                    candidate_disables_inside_saved_scope=True,
                    end_restores_scissor_enable=True,rectangle_coordinates_unchanged=True),
                proposed_geometry=[[562,438,64,6],[562,456,64,6],
                                   [562,444,2,12],[624,444,2,12],[564,444,22,12]],
                limits=['Original rectangle wrapper changes/uses shared drawing state and color.',
                        'Basic ABI fixture intercepts enter/leave; extended state fixture executes them and native transform stacks.',
                        'Queue fixture executes native rectangle/vertex/index/batch code; buffer resources, shader and GPU boundary remain simulated.',
                        'Native queue submit discards final draw result; success is not LCD completion.',
                        'Synthetic active scope is not evidence that a live post callback has an active rectangle context; do not nest native begin blindly inside post.',
                        'Must preserve native render state, establish drawing-thread lifetime and retirement before a live trial.',
                        'Post callback is before present, not after GPU/LCD completion.',
                        'No new font subsystem, loader or production integration implemented.'])


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--research',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();im=Image(a.research/IMAGES['obj'][0],IMAGES['obj'][1])
    try: result=audit(im)
    finally: im.stream.close()
    with a.output.open('x') as f: json.dump(result,f,indent=2);f.write('\n')
    print(a.output)

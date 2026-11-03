#!/usr/bin/env python3
"""Read pinned A7C 2.00 module descriptors offline; never send load messages."""
import argparse
import json
import struct
from pathlib import Path

from audit_ui_contract import Image

IM = ('evidence/camera-2.00-display-runtime/usr__bin__im.elf',
      'fca372d437333271f5d21c880768c02a99509bcc2629e3ba00122fb7a9f716af')
IMDB = ('evidence/camera-2.00-resume/usr__lib__libIMDB.so',
        'ccba306691b39b627634d52c93e08bdec3f403bc27524de8f92cf4d5e0596bee')


def cstring(image, address):
    if not address:
        return ''
    value = bytearray()
    for offset in range(512):
        byte = image.read(address+offset, 1)
        if byte == b'\0':
            return value.decode('ascii')
        value.extend(byte)
    raise ValueError('Unterminated module descriptor string')


def audit(im, imdb):
    entries = []
    start = imdb.symbols['imdb_raw']['st_value'] + 0x84
    for i in range(300):
        address = start + i*44
        words = struct.unpack('<11I', imdb.read(address, 44))
        if words[0] == 40:
            break
        entries.append({
            'address': hex(address), 'type': hex(words[0]),
            'phase_mask': hex(words[1]), 'target_mask': hex(words[2]),
            'id': words[3] & 65535, 'dependency_field': words[3] >> 16,
            'path': cstring(imdb, words[4]),
            'callbacks': [cstring(imdb, x) for x in words[5:]],
        })
    else:
        raise ValueError('Module table terminator missing')
    if len(entries) != 209:
        raise ValueError('Unexpected module count')
    messages = {name: hex(im.u32(address)) for name, address in
                [('load', 0x9898), ('unload', 0x989c), ('forward_exec', 0x98a0)]}
    if messages != {'load': '0x940021', 'unload': '0x940022', 'forward_exec': '0x940023'}:
        raise ValueError('Unexpected dispatch literals')
    if (im.u32(0xa43c), im.u32(0x9890), im.u32(0x9894),
        im.u32(0xaf4c), cstring(im, im.u32(0xaf54))) != (
            0x94016a, 0x9400e1, 0x12345678, 0x94020a, '%s'):
        raise ValueError('Unexpected queue, identity or forwarding literals')
    return {
        'scope': 'Offline descriptor/dispatch audit; no camera access, registration, load, unload or patch',
        'sources': {'im': IM[1], 'imdb': IMDB[1]},
        'dispatch': '0x97ec', 'messages': messages,
        'sync_queue': '0x94016a',
        'identity': {'operation': '0x9400e1', 'magic': '0x12345678',
                     'state_read_address': '0x15424'},
        'forward_exec': {'body': '0xaeac', 'destination': '0x94020a',
                         'format': '%s', 'readonly': False,
                         'note': 'bootin copies a command string and calls its fork/execve helper; not a module query.'},
        'load_body': '0xb698', 'type_dispatch': '0xb594',
        'dlopen_body': '0xb3b8', 'dlopen_with_init_argument': '0xb304',
        'unload_body': '0xb8a8',
        'entry_start': hex(start), 'entry_stride': 44, 'entries': entries,
        'limits': [
            'Load request carries a module ID, not an arbitrary pathname.',
            'IMDB_find_entry also filters the current target mask.',
            'An already loaded module follows reference/owner bookkeeping, not necessarily dlopen again.',
            'A test/sample name does not prove an unused or harmless live entry.',
            '0x940023 forwards an execution request; never use it as a read-only query.',
            'No verified custom registration or external sender/reply contract yet.',
            'Do not alter live module tables or invoke test modules based on this report.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    im = Image(args.research/IM[0], IM[1])
    try:
        imdb = Image(args.research/IMDB[0], IMDB[1])
        try:
            result = audit(im, imdb)
        finally:
            imdb.stream.close()
    finally:
        im.stream.close()
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('Offline module audit: 209 descriptors; no camera operations.')
    print(args.output)


if __name__ == '__main__':
    main()

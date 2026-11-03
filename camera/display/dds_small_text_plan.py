"""24px-high UPLOAD strip for native DDS x2/y6; offline font asset only.

Pack a whole word across the 8px glyph cells so native 16px character advances
no longer force wide spacing. Four authored source rows become 24 screen rows.
The existing 128-byte RAM font transaction and corner aperture stay unchanged.
"""

def compile_upload_24():
    glyphs = {
        'U': ['10001', '10001', '10001', '01110'],
        'P': ['11110', '10001', '11110', '10000'],
        'L': ['10000', '10000', '10000', '11111'],
        'O': ['01110', '10001', '10001', '01110'],
        'A': ['01110', '10001', '11111', '10001'],
        'D': ['11110', '10001', '10001', '11110'],
    }
    rows = ['0' * 64]
    rows += [('0' + '0'.join(glyphs[c][y] for c in 'UPLOAD')).ljust(64, '0') for y in range(4)]
    rows += ['0' * 64] * 3
    tiles = [bytes(int(row[x:x+8], 2) for row in rows) for x in range(0, 64, 8)]
    unique = [bytes(8)]
    for tile in tiles:
        if tile not in unique:
            unique.append(tile)
    indices = [unique.index(tile) for tile in tiles] + [0]*8
    payload = bytes((indices[i] << 4) | indices[i+1] for i in range(0, 16, 2))
    font = b''.join(unique).ljust(128, b'\0')
    assert len(font) == 128 and len(payload) == 8
    return font, payload


def compile_progress_24(percent=0):
    """Fixed 13-glyph font; compact UD ligature, two digits and percent.

    Native DDS advances 16 screen pixels per cell. Packing UD into one cell
    keeps the whole label in the already verified 78px shooting aperture.
    Only the eight-byte message changes at runtime; the font stays constant.
    """
    if not isinstance(percent, int) or not 0 <= percent <= 99:
        raise ValueError('progress must be 0..99')
    glyphs = [
        ['0000000']*4,
        ['1010110', '1010101', '1010101', '0100110'],  # UD
        ['01110', '10001', '10001', '01110'],
        ['00100', '01100', '00100', '01110'],
        ['11110', '00001', '01100', '11111'],
        ['11110', '00110', '00001', '11110'],
        ['10010', '10010', '11111', '00010'],
        ['11111', '10000', '01110', '11110'],
        ['01110', '10000', '11110', '11110'],
        ['11111', '00010', '00100', '01000'],
        ['01110', '11111', '10001', '01110'],
        ['01110', '10001', '01111', '00001'],
        ['11001', '00010', '01000', '10011'],
    ]
    font = b''.join(bytes([0]+[int(row, 2) << (1 if len(row)==7 else 2)
                               for row in rows]+[0]*3) for rows in glyphs).ljust(128, b'\0')
    tens = 0 if percent < 10 else 2+percent//10
    payload = bytes([0x10 | tens, ((2+percent % 10) << 4) | 12]+[0]*6)
    return font, payload


def compile_progress_bar_24(percent=0):
    """64x24 framed bar using sixteen fixed glyphs, including blank zero.

    Left/middle/right tiles each have five prefix widths (0,2,4,6,8).
    Four tiles form a closed frame with sixteen visible progress states.
    Native x2/y6 scaling is retained; no runtime font changes or blinking.
    99% leaves the last interior source column empty until normal cleanup.
    """
    if not isinstance(percent, int) or not 0 <= percent <= 99:
        raise ValueError('progress must be 0..99')
    glyphs = [bytes(8)]
    for border in (128, 0, 1):
        for width in range(0, 9, 2):
            fill = ((255 << (8 - width)) & 255) | border
            glyphs.append(bytes([0, 255, fill, fill, 255, 0, 0, 0]))
    font = b''.join(glyphs)
    steps = percent * 16 // 100
    indices = [base + min(4, max(0, steps - tile * 4))
               for tile, base in enumerate((1, 6, 6, 11))] + [0] * 12
    payload = bytes((indices[i] << 4) | indices[i + 1] for i in range(0, 16, 2))
    return font, payload

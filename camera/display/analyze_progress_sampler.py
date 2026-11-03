"""Summarize bounded v2 sampler logs; samples are not atomic LCD captures."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re


def analyze(text):
    header = re.search(r'SAMPLER version=2 began_ms=(\d+) end_ms=(\d+) samples=(\d+) rc=(\d+) unmap=(\d+) close=(\d+),(\d+)', text)
    if not header:
        raise ValueError('Missing v2 completion record')
    begin, end, count, rc, unmap, close1, close2 = map(int, header.groups())
    rows, elapsed = [], 0
    for index, data in re.findall(r'^R index=(\d+) data=([a-f0-9]+)$', text, re.M):
        raw = bytes.fromhex(data)
        if int(index) != len(rows) or len(raw) % 10:
            raise ValueError('Incomplete or out-of-order samples')
        for at in range(0, len(raw), 10):
            dt, flags, level, zero, lo0, lo1, hi0, hi1, control, redraw = raw[at:at+10]
            elapsed += dt
            rows.append(dict(ms=elapsed, dt=dt, mask=flags & 63,
                             enabled=bool(flags & 128), visible=bool(flags & 64),
                             level=level, zero=zero, low=lo0 | lo1 << 8,
                             high=hi0 | hi1 << 8, controls=control, redraw=redraw))
    if len(rows) != count or not rows:
        raise ValueError('Sample count mismatch or empty sample set')
    blank = [r for r in rows if r['mask'] == 0]
    return dict(
        scope='Sequential physical-memory samples, not LCD scanout or GPU completion proof',
        begin_ms=begin, end_ms=end, samples=count, rc=rc, unmap=unmap, close=[close1, close2],
        max_dt_ms=max(r['dt'] for r in rows), capped_dt=sum(r['dt'] == 255 for r in rows),
        full=sum(r['mask'] == 63 for r in rows), blank=len(blank),
        partial=sum(r['mask'] not in (0, 63) for r in rows),
        disabled=sum(not r['enabled'] for r in rows), invisible=sum(not r['visible'] for r in rows),
        invalid_payload=sum(r['level'] == 255 for r in rows),
        blank_values=Counter('%04x..%04x' % (r['low'], r['high']) for r in blank),
        blank_zero_masks=Counter(str(r['zero']) for r in blank),
        controls_all=Counter(str(r['controls']) for r in rows),
        controls_while_blank=Counter(str(r['controls']) for r in blank),
        redraw_all=Counter(str(r['redraw']) for r in rows),
        redraw_while_blank=Counter(str(r['redraw']) for r in blank),
        by_level={str(k): {'samples': sum(r['level'] == k for r in rows),
                          'blank': sum(r['level'] == k for r in blank)}
                  for k in sorted({r['level'] for r in rows})})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.log.read_text()), indent=2))

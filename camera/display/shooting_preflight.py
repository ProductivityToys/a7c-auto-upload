"""Host-only gate for the verified shooting aperture in fresh STATUS metadata.

This is not a layout query or proof that the current bitmap uses this aperture.
The camera still checks the descriptor and mapping immediately before reading.
"""
import re


def require_shooting_mapping(response):
    if response.get('action') != 'STATUS' or response.get('rc') != 0:
        raise ValueError('Successful fresh STATUS required; do not send PROBE')
    report = response.get('report', '')
    marker = 'CURRENT_SHARED_MAPS_LIMIT_BYTES=12000\n'
    if report.count(marker) != 1:
        raise ValueError('Current native mapping unavailable; do not send PROBE')
    tail = report.split(marker, 1)[1]
    if tail.count('A7C_DEBUG_END') != 1:
        raise ValueError('Incomplete STATUS; do not send PROBE')
    maps = tail.split('A7C_DEBUG_END', 1)[0]
    matches = re.findall(
        r'^([0-9a-f]+)-([0-9a-f]+) rw-s fe33a000 \S+ \d+\s+/dev/mem$',
        maps, re.M)
    if len(matches) != 1:
        raise ValueError('Shooting aperture not unique/present; do not send PROBE')
    lo, hi = (int(value, 16) for value in matches[0])
    if not (0 < lo < hi <= 0x80000000 and hi - lo == 614400):
        raise ValueError('Unexpected shooting mapping extent; do not send PROBE')
    return lo, hi

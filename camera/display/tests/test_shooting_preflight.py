import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shooting_preflight import require_shooting_mapping


class ShootingPreflightTests(unittest.TestCase):
    line = '14714000-147aa000 rw-s fe33a000 fc:07 136 /dev/mem\n'

    def response(self, maps):
        return dict(action='STATUS', rc=0, report='A7C_DEBUG_V2\n'
                    'CURRENT_SHARED_MAPS_LIMIT_BYTES=12000\n' + maps + '\nA7C_DEBUG_END\n')

    def test_known_mapping_and_moving_virtual_address(self):
        self.assertEqual(require_shooting_mapping(self.response(self.line)), (0x14714000, 0x147aa000))
        self.assertEqual(require_shooting_mapping(self.response(self.line.replace(
            '14714000-147aa000', '14cee000-14d84000'))), (0x14cee000, 0x14d84000))

    def test_reject_playback_wrong_size_permissions_and_duplicates(self):
        for maps in ('', self.line.replace('/dev/mem', '/dev/stream'),
                     self.line.replace('fe33a000', '22b48000'),
                     self.line.replace('147aa000', '147ab000'),
                     self.line.replace('rw-s', 'rw-p'), self.line * 2):
            with self.subTest(maps=maps), self.assertRaises(ValueError):
                require_shooting_mapping(self.response(maps))

    def test_old_log_cannot_substitute_for_current_map(self):
        r = self.response('')
        r['report'] = self.line + r['report']
        with self.assertRaises(ValueError):
            require_shooting_mapping(r)
        for key, value in [('action', 'PROBE'), ('rc', 1), ('report', 'CURRENT_SHARED_MAPS_UNAVAILABLE')]:
            r = self.response(self.line); r[key] = value
            with self.assertRaises(ValueError):
                require_shooting_mapping(r)


if __name__ == '__main__':
    unittest.main()

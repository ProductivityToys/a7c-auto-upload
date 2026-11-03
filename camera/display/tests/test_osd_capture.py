"""Bounded offline decoding of experimental camera captures."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location("decode_osd", Path(__file__).parents[1] / "decode_osd.py")
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


class CaptureTests(unittest.TestCase):
    def test_long_runs_and_values(self):
        runs = [(65535, 0)] * 4 + [(45060, 0xABCD)]
        packed = b"A7R1" + struct.pack("<I", 614400) + b"".join(struct.pack("<HH", *r) for r in runs)
        self.assertEqual(decoder.unpack_capture(packed), b"\0\0" * 262140 + b"\xcd\xab" * 45060)

    def test_bad_runs_and_lengths(self):
        header = b"A7R1" + struct.pack("<I", 614400)
        invalid = [header, header + b"x", header + struct.pack("<HH", 0, 0),
                   header + struct.pack("<HH", 1, 0),
                   header + struct.pack("<HH", 65535, 0) * 5,
                   b"A7R1" + struct.pack("<IHH", 2, 1, 0),
                   header + b"\0" * 98304, b"short raw"]
        for data in invalid:
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                decoder.unpack_capture(data)

    def test_raw_remains_supported(self):
        raw = b"\x12\x34" * 307200
        self.assertEqual(decoder.unpack_capture(raw), raw)

    def test_raw_pixel_prefix_is_not_a_codec_header(self):
        raw = b"A7R1" + bytes(614396)
        self.assertEqual(decoder.unpack_capture(raw), raw)


if __name__ == "__main__":
    unittest.main()

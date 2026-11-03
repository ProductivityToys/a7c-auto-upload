import sys
import struct
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dds_text_plan import compile_text, render_slot_zero
from dds_small_text_plan import compile_upload_24, compile_progress_24, compile_progress_bar_24


class TextPlanBounds(unittest.TestCase):
    def test_progress_bar_fixed_font_geometry_and_transparent_tail(self):
        font, _ = compile_progress_bar_24()
        payloads=set()
        for percent in range(100):
            f,m=compile_progress_bar_24(percent);payloads.add(m)
            self.assertEqual(f,font);self.assertEqual(len(f),128)
            self.assertEqual(m[2:],bytes(6));self.assertEqual(f[:8],bytes(8))
            raw=struct.unpack('<307200H',render_slot_zero(f,m,origin=(562,432),clip_to_screen=True))
            filled=max(0,percent*16//100*4-2)
            for y in range(438,462):
                expected=64 if y<444 or y>=456 else filled+4
                self.assertEqual(sum(v==0xffff for v in raw[y*640:(y+1)*640]),expected)
            self.assertEqual(sum(v==0xffff for v in raw),filled*12+4*12+64*12)
        self.assertEqual(len(payloads),16)
        for value in [-1,100,'42']:
            with self.assertRaises(ValueError):compile_progress_bar_24(value)

    def test_progress_font_is_static_and_all_labels_fit_existing_aperture(self):
        font, _ = compile_progress_24()
        payloads = set()
        for percent in range(100):
            current, payload = compile_progress_24(percent)
            self.assertEqual(current, font)
            payloads.add(payload)
            # Four cells occupy 64 pixels; all authored ink fits the same
            # 24px-high strip. No font or coordinate rewrite on each update.
            self.assertEqual(payload[0] >> 4, 1)
            self.assertEqual(payload[1] & 15, 12)
            self.assertEqual(payload[2:], bytes(6))
        self.assertEqual(len(payloads), 100)
        for percent in [0, 9, 42, 99]:
            f, marker = compile_progress_24(percent)
            raw=struct.unpack('<307200H', render_slot_zero(f,marker,origin=(562,432),clip_to_screen=True))
            ink=[(i%640,i//640) for i,v in enumerate(raw) if v==0xffff]
            self.assertTrue(all(562<=x<640 and 438<=y<462 for x,y in ink))
        for value in [-1,100,'42']:
            with self.assertRaises(ValueError):compile_progress_24(value)

    def test_small24_clears_iso_and_fits_narrower_aperture(self):
        font, payload = compile_upload_24()
        full = struct.unpack('<307200H', render_slot_zero(font, payload, origin=(0, 0)))
        clipped = struct.unpack('<307200H', render_slot_zero(
            font, payload, origin=(562, 432), clip_to_screen=True))
        ink = [(x, y) for y in range(480) for x in range(640)
               if clipped[y*640+x] == 0xffff]
        self.assertEqual(len(ink), sum(v == 0xffff for v in full))
        self.assertEqual(len(ink), 744)
        self.assertEqual((min(x for x, y in ink), max(x for x, y in ink),
                          min(y for x, y in ink), max(y for x, y in ink)),
                         (564, 633, 438, 461))
        self.assertFalse(any(clipped[y*640+x] for y in range(480)
                             for x in range(640) if x < 562 or y < 432))

    def test_shooting_corner_keeps_all_upload_ink(self):
        font, payload, _ = compile_text(["UPLOAD", "TEST"])
        full = struct.unpack("<307200H", render_slot_zero(font, payload, origin=(0, 0)))
        clipped = struct.unpack("<307200H", render_slot_zero(
            font, payload, origin=(548, 432), clip_to_screen=True))
        self.assertEqual(sum(v == 0xffff for v in full[:640*48]),
                         sum(v == 0xffff for v in clipped))
        self.assertTrue(all(v == 0 for y in range(480) for x in range(640)
                            if (x < 548 or y < 432) for v in [clipped[y*640+x]]))

    def test_explicit_corner_clipping_preserves_source_scale(self):
        font, payload, _ = compile_text(["UPLOAD", "TEST"])
        full = struct.unpack("<307200H", render_slot_zero(font, payload, origin=(0, 0)))
        clipped = struct.unpack("<307200H", render_slot_zero(
            font, payload, origin=(536, 432), clip_to_screen=True))
        for y in range(480):
            for x in range(640):
                self.assertEqual(clipped[y*640+x], full[(y-432)*640+x-536]
                                 if x >= 536 and y >= 432 else 0)
        for origin in ((640, 0), (0, 480), (-1, 0), (0, -1)):
            with self.assertRaises(ValueError):
                render_slot_zero(font, payload, origin=origin, clip_to_screen=True)

    def test_fixed_payload_and_distinct_letters(self):
        font, payload, alphabet = compile_text(["UPLOAD", "42% 1/3"])
        self.assertEqual((len(font), len(payload)), (128, 8))
        decoded = "".join(alphabet[n] for byte in payload for n in (byte >> 4, byte & 15))
        self.assertEqual(decoded, "UPLOAD  42% 1/3 ")
        self.assertEqual(font[:8], bytes(8))

    def test_no_truncation_or_implicit_glyph_fallback(self):
        for lines in (["UPLOADING", "TEST"], ["upload", ""], ["上传", ""],
                      ["A"], ["A", "B", "C"], ["01234567", "89ADEGIL"]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                compile_text(lines)

    def test_reject_rectangle_and_pixel_contract_overflow(self):
        font, payload, _ = compile_text(["UPLOAD", "TEST"])
        for origin in ((65, 0), (0, 289), (-1, 0), (0, -1)):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                render_slot_zero(font, payload, origin=origin)
        for kwargs in ({"foreground": 65536}, {"blank": -1}):
            with self.assertRaises(ValueError):
                render_slot_zero(font, payload, **kwargs)
        with self.assertRaises(ValueError):
            render_slot_zero(font[:-1], payload)
        with self.assertRaises(ValueError):
            render_slot_zero(font, payload + b"\x00")


if __name__ == "__main__":
    unittest.main()

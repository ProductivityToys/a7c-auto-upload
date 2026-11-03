import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location("native_font", Path(__file__).parents[1] / "native_font.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    tags = [b"cmap", b"glyf", b"loca", b"head", b"maxp"]
    font = bytearray(struct.pack(">IHHHH", 0x10000, 5, 0, 0, 0))
    for n, tag in enumerate(tags):
        font.extend(struct.pack(">4sIII", tag, 0, 92 + n * 4, 4))
    font.extend(bytes(20))
    head = b"LTT\n7\n2\n".ljust(1024, b" ")
    entry = b"Univers\nUniversOTS-SJ.ttf\nembeddedoffset=2560\nembeddedsize=112\n"
    return head + entry.ljust(512, b" ") + bytes([32]) * 1024 + font


class NativeFontTests(unittest.TestCase):
    def test_exact_embedded_range(self):
        data = fixture()
        font, metadata = module.extract_embedded(data)
        self.assertEqual(font, data[2560:])
        self.assertEqual(metadata["bytes"], 112)

    def test_container_bounds_and_duplicate_entries(self):
        original = fixture()
        invalid = [original[:-1], original[:100],
                   original.replace(b"embeddedoffset=2560", b"embeddedoffset=0000"),
                   original[:1536] + original[1024:1536] + original[2048:],
                   original.replace(b"embeddedsize=112", b"embeddedsize=999")]
        for data in invalid:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                module.extract_embedded(data)

    def test_sfnt_bounds_and_duplicate_tables(self):
        data = bytearray(fixture())
        struct.pack_into(">I", data, 2560 + 12 + 8, 0xfffffff0)
        with self.assertRaises(ValueError):
            module.extract_embedded(data)
        data = bytearray(fixture())
        data[2560 + 28:2560 + 32] = b"cmap"
        with self.assertRaises(ValueError):
            module.extract_embedded(data)

    def test_never_accept_path_as_entry_name(self):
        with self.assertRaises(ValueError):
            module.extract_embedded(fixture(), "../../font.ttf")


if __name__ == "__main__":
    unittest.main()

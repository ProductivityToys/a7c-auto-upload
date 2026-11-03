"""Offline extraction of an owner's embedded sfnt font; no camera operations.

Sony's LTT font-linking container can embed ordinary TTF files. Keep extracted
fonts in private research storage: they are not application release assets.
This does not reproduce TextRM rasterization or authorize an on-camera draw.
"""
import argparse
import hashlib
import io
import json
import re
import struct
from pathlib import Path


def extract_embedded(data, filename="UniversOTS-SJ.ttf"):
    if not data.startswith(b"LTT\n7\n2\n"):
        raise ValueError("Unsupported LTT container")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.ttf", filename):
        raise ValueError("Expected a font basename")
    # This container's directory occupies the first 2560 bytes. Do not search
    # binary glyph data for metadata or silently select duplicate font names.
    if len(data) < 2560:
        raise ValueError("Truncated LTT directory")
    header = data[:2560].decode("ascii", errors="strict")
    blocks = [header[pos:pos + 512] for pos in (1024, 1536, 2048)
              if "\n" + filename + "\n" in header[pos:pos + 512]]
    if len(blocks) != 1:
        raise ValueError("Embedded font entry missing or ambiguous")
    block = blocks[0]
    values = {}
    for key in ("embeddedoffset", "embeddedsize"):
        matches = re.findall(r"^" + key + r"=([0-9]+)$", block, re.M)
        if len(matches) != 1:
            raise ValueError("Missing or duplicate " + key)
        values[key] = int(matches[0])
    offset, size = values["embeddedoffset"], values["embeddedsize"]
    if offset < 2560 or size < 12 or offset + size > len(data):
        raise ValueError("Embedded font outside container")
    font = data[offset:offset + size]
    if font[:4] != b"\0\1\0\0":
        raise ValueError("Expected TrueType sfnt")
    count = struct.unpack_from(">H", font, 4)[0]
    if not 1 <= count <= 128 or 12 + count * 16 > size:
        raise ValueError("Invalid sfnt directory")
    tables = {}
    for n in range(count):
        tag, _, start, length = struct.unpack_from(">4sIII", font, 12 + 16 * n)
        if tag in tables or start < 12 + 16 * count or start + length > size:
            raise ValueError("Invalid or duplicate sfnt table")
        tables[tag] = (start, length)
    if not {b"cmap", b"glyf", b"loca", b"head", b"maxp"} <= tables.keys():
        raise ValueError("Required glyph tables missing")
    return font, {"filename": filename, "offset": offset, "bytes": size,
                  "container_sha256": hashlib.sha256(data).hexdigest(),
                  "font_sha256": hashlib.sha256(font).hexdigest(),
                  "tables": [t.decode("ascii") for t in tables]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--container", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--preview", action="store_true", help="Host FreeType rendering, not camera output")
    a = p.parse_args()
    font, report = extract_embedded(a.container.read_bytes())
    a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    path = a.output / "UniversOTS-SJ.private.ttf"
    with path.open("xb") as f:
        path.chmod(0o600)
        f.write(font)
    report.update(scope="Offline owner-supplied font extraction; no camera access",
                  camera_render_verified=False, redistribute_font=False)
    if a.preview:
        from PIL import Image, ImageDraw, ImageFont
        face = ImageFont.truetype(io.BytesIO(font), 32)
        canvas = Image.new("L", (520, 60))
        ImageDraw.Draw(canvas).text((2, 2), "UD 42% 0123456789", font=face, fill=255)
        canvas.save(a.output / "host-font-preview.png")
        report["preview"] = "Host Pillow/FreeType at 32 px; not Sony TextRM or an LCD screenshot"
        report["font_name"] = face.getname()
    (a.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

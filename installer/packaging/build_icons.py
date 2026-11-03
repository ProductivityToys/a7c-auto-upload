"""Render repository-native SVG artwork to macOS/Windows icons (Qt + iconutil)."""
import argparse
from pathlib import Path
import subprocess
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--work', type=Path, required=True)
a = p.parse_args()
assets = Path(__file__).resolve().parent / 'assets'
iconset = a.work / 'app.iconset'
iconset.mkdir(parents=True, exist_ok=True)
svg = QSvgRenderer(str(assets / 'app.svg'))
for logical in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        size = logical * scale
        canvas = QImage(QSize(size, size), QImage.Format_ARGB32)
        canvas.fill(0)
        painter = QPainter(canvas)
        svg.render(painter)
        painter.end()
        canvas.save(str(iconset / f'icon_{logical}x{logical}{"@2x" if scale == 2 else ""}.png'))
subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(assets / 'app.icns')], check=True)
assert QImage(str(iconset / 'icon_256x256.png')).save(str(assets / 'app.ico'), 'ICO')

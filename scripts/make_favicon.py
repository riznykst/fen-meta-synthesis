"""Generate the favicon (no external asset): a dark slate tile with the accent
"F" mark used by the portal header. Writes an .ico and a 180px PNG (touch icon).
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "portal"

BG = (15, 23, 42)
ACCENT = (129, 140, 248)


def render(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", int(size * 0.68))
    text = "F"
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.text(
        ((size - width) / 2 - box[0], (size - height) / 2 - box[1] - size * 0.02),
        text,
        font=font,
        fill=ACCENT,
    )
    return image


sizes = [16, 32, 48, 64]
frames = [render(s) for s in sizes]
frames[-1].save(OUT / "favicon.ico", format="ICO", sizes=[(s, s) for s in sizes])
render(180).save(OUT / "apple-touch-icon.png")
print("wrote", OUT / "favicon.ico", "and apple-touch-icon.png")

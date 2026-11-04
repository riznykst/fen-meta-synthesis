"""Render the closing end card (1280x800 PNG) for the demo video.

Dark slate background matching the portal palette, Georgia for the slogan,
Segoe UI for the links. No external assets: fonts come from C:/Windows/Fonts.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "video" / "endcard.png"

W, H = 1280, 800
BG = (15, 23, 42)          # slate-900
FG = (241, 245, 249)       # slate-100
MUTED = (148, 163, 184)    # slate-400
ACCENT = (129, 140, 248)   # indigo-400

GEORGIA = "C:/Windows/Fonts/georgia.ttf"
SEGOE = "C:/Windows/Fonts/segoeui.ttf"
SEGOE_BOLD = "C:/Windows/Fonts/segoeuib.ttf"


def centered(draw: ImageDraw.ImageDraw, text: str, font, y: int, fill) -> None:
    width = draw.textbbox((0, 0), text, font=font)[2]
    draw.text(((W - width) / 2, y), text, font=font, fill=fill)


def main() -> int:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    slogan = ImageFont.truetype(GEORGIA, 44)
    thanks = ImageFont.truetype(GEORGIA, 30)
    link = ImageFont.truetype(SEGOE, 24)
    label = ImageFont.truetype(SEGOE_BOLD, 20)

    centered(draw, "AI proposes. Evidence challenges.", slogan, 210, FG)
    centered(draw, "Humans decide.", slogan, 266, ACCENT)

    draw.line([(W / 2 - 60, 360), (W / 2 + 60, 360)], fill=MUTED, width=2)

    centered(draw, "Thank you for watching", thanks, 392, FG)

    centered(draw, "LIVE DEMO", label, 486, MUTED)
    centered(draw, "fen-meta-synthesis.vercel.app", link, 514, ACCENT)

    centered(draw, "CODE", label, 576, MUTED)
    centered(draw, "github.com/riznykst/fen-meta-synthesis", link, 604, ACCENT)

    centered(draw, "FEN x Meta  ·  Meta Global AI Developer Hackathon", link, 700, MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

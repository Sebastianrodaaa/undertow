#!/usr/bin/env python3
"""Generate the black-and-white README banner from public-domain art."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 400


def dither_side(path: Path, mirror: bool = False) -> Image.Image:
    img = Image.open(path).convert("L")
    img = ImageOps.autocontrast(img, cutoff=1)
    # Engravings are black ink on white paper. Invert so the lines become white
    # ink on the black banner, then reduce to one bit.
    img = ImageOps.invert(img)
    scale = H / img.height
    img = img.resize((int(img.width * scale), H), Image.Resampling.LANCZOS)
    if img.width > 260:
        left = max(0, (img.width - 260) // 2)
        img = img.crop((left, 0, left + 260, H))
    if mirror:
        img = ImageOps.mirror(img)
    img = ImageEnhance.Contrast(img).enhance(1.25)
    return img.convert("1").convert("L")


def paste_fading(base: Image.Image, art: Image.Image, side: str) -> None:
    mask = Image.new("L", art.size, 0)
    px = mask.load()
    for x in range(art.width):
        t = x / max(1, art.width - 1)
        strength = int(112 * math.sin(math.pi * t))
        for y in range(art.height):
            px[x, y] = strength
    # Keep the outside edge fully black as well; the strongest ink sits inward
    # and then disappears into the center.
    base.paste(art, (0 if side == "left" else W - art.width, 0), mask)


def main() -> None:
    out = ROOT / "docs/screenshots/banner.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    banner = Image.new("RGB", (W, H), "black")
    paste_fading(banner, dither_side(ROOT / "docs/art/deluge.jpg"), "left")
    paste_fading(banner, dither_side(ROOT / "docs/art/pont-neuf-1844.jpg", mirror=True), "right")

    draw = ImageDraw.Draw(banner)
    blackletter = ImageFont.truetype(str(ROOT / "app/fonts/UnifrakturMaguntia-Book.ttf"), 116)
    mono = ImageFont.truetype(str(ROOT / "app/fonts/GeistMono-Regular.woff2"), 22)
    title = "undertow"
    box = draw.textbbox((0, 0), title, font=blackletter)
    tw, th = box[2] - box[0], box[3] - box[1]
    # Render oversized and quantize softly to evoke a bitmap blackletter face.
    tx = Image.new("L", (tw + 12, th + 12), 0)
    td = ImageDraw.Draw(tx)
    td.text((6 - box[0], 4 - box[1]), title, font=blackletter, fill=255)
    tx = tx.resize((tx.width // 2, tx.height // 2), Image.Resampling.NEAREST).resize((tx.width, tx.height), Image.Resampling.NEAREST)
    banner.paste(Image.new("RGB", tx.size, "white"), ((W - tx.width) // 2, 92), tx)
    tag = "a neural net floods a city with directions. close a bridge and the tide pulls back."
    tb = draw.textbbox((0, 0), tag, font=mono)
    draw.text(((W - (tb[2] - tb[0])) / 2, 260), tag, font=mono, fill=(210, 210, 210))
    banner.save(out)
    print(out)


if __name__ == "__main__":
    main()

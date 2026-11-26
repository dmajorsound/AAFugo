"""Draw the AAFUGO icon images for the installers (same sizes and places as Ahh 1.1.1).

usage: python3 make_branding.py
  mac_ui/icon.png            256 x 256, transparent  (welcome page, shown at 96 px)
  win/welcome-icon-100/200   72 / 144, white         (welcome page, middle)
  win/small-100/200          55 x 58 / 110 x 116     (later pages, top right)
  win/wizard-100/200         164 x 314 / 328 x 628   (finish page, icon in the middle, no logo)
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE = (76, 147, 220)


def icon(size):
    """The AAFUGO icon (blue rounded square, two clips like OLAAF, a paper plane taking off), drawn 4x and scaled down."""
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = S / 120.0
    P = lambda pts: [(x * k, y * k) for x, y in pts]
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=28 * k, fill=BLUE)
    d.polygon(P([(88, 10), (40, 34), (62, 32)]), fill="white")
    d.polygon(P([(88, 10), (62, 32), (61, 47)]), fill=(214, 230, 247))
    d.polygon(P([(46, 68), (58, 52), (86, 52), (98, 68)]), fill="white")
    d.polygon(P([(22, 90), (22, 74), (52, 74), (62, 90)]), fill="white")
    return im.resize((size, size), Image.LANCZOS)


def on_white(w, h, size, x, y, path):
    im = Image.new("RGB", (w, h), "white")
    ic = icon(size)
    im.paste(ic, (x, y), ic)
    im.save(path)


if __name__ == "__main__":
    icon(256).save(os.path.join(HERE, "mac_ui", "icon.png"))
    W = os.path.join(HERE, "win")
    on_white(72, 72, 72, 0, 0, os.path.join(W, "welcome-icon-100.bmp"))
    on_white(144, 144, 144, 0, 0, os.path.join(W, "welcome-icon-200.bmp"))
    on_white(55, 58, 46, 4, 6, os.path.join(W, "small-100.bmp"))
    on_white(110, 116, 92, 9, 12, os.path.join(W, "small-200.bmp"))
    on_white(164, 314, 84, 40, 115, os.path.join(W, "wizard-100.bmp"))
    on_white(328, 628, 168, 80, 230, os.path.join(W, "wizard-200.bmp"))
    print("wrote installer images")

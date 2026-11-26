"""Draw the AAFUGO icon images for the installers (same sizes and places as Ahh 1.1.1).

usage: python3 make_branding.py
  mac_ui/icon.png            256 x 256, transparent  (welcome page, shown at 96 px)
  win/welcome-icon-100/200   72 / 144, white         (welcome page, middle)
  win/small-100/200          55 x 58 / 110 x 116     (later pages, top right)
  win/wizard-100/200         164 x 314 / 328 x 628   (finish page, icon in the middle, no logo)
"""
import os

import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE = (76, 147, 220)


from icon_art import icon  # noqa: E402


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

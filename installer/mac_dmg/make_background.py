"""Draw the AAFUGO disk image background (640 x 420 and @2x), same layout as OLAAF's installer/mac_dmg.

usage: python3 make_background.py <IBM Plex font dir> <out dir>
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

NAME = "AAFUGO"
SUBTITLE = "Session Export for Reaper"
BLUE = (76, 147, 220)
INK = (30, 30, 30)
MUTE = (110, 110, 110)
LINE = (226, 226, 226)
STEPS = [
    ("1", ["Double-click Install %s and click through." % NAME]),
    ("2", ["macOS says it can’t be opened? Click Done, then double-click",
           "Blocked? Open Privacy & Security, scroll down and click Open Anyway."]),
    ("3", ["Double-click Install %s again and choose Open." % NAME]),
]
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mac_ui", "logo.png")
FOOT = "Quit REAPER first. The installer is free and not signed by Apple, so macOS asks once."


def icon(d, x, y, size, s):
    """The AAFUGO icon: blue rounded square, two clips like OLAAF, a paper plane taking off (120-unit grid)."""
    k = size * s / 120.0
    P = lambda pts: [(x * s + px * k, y * s + py * k) for px, py in pts]
    d.rounded_rectangle([x * s, y * s, x * s + size * s, y * s + size * s], radius=28 * k, fill=BLUE)
    d.polygon(P([(88, 10), (40, 34), (62, 32)]), fill="white")
    d.polygon(P([(88, 10), (62, 32), (61, 47)]), fill=(214, 230, 247))
    d.polygon(P([(46, 68), (58, 52), (86, 52), (98, 68)]), fill="white")
    d.polygon(P([(22, 90), (22, 74), (52, 74), (62, 90)]), fill="white")


def badge(d, cx, cy, r, text, f, s):
    d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=BLUE)
    d.text((cx * s, cy * s), text, font=f, fill="white", anchor="mm")


def draw(fonts, s):
    im = Image.new("RGB", (640 * s, 420 * s), "white")
    d = ImageDraw.Draw(im)
    F = lambda name, px: ImageFont.truetype(os.path.join(fonts, name), int(px * s))
    bold, reg, small, num = F("IBMPlexSans-Bold.ttf", 19), F("IBMPlexSans-Regular.ttf", 13), \
        F("IBMPlexSans-Regular.ttf", 10.5), F("IBMPlexSans-Bold.ttf", 11)
    step = F("IBMPlexSans-Regular.ttf", 12.5)
    # header: icon, name bold, subtitle grey, a line
    icon(d, 24, 20, 28, s)
    d.text((62 * s, 34 * s), NAME, font=bold, fill=INK, anchor="lm")
    nw = d.textlength(NAME, font=bold) / s
    d.text(((62 + nw + 12) * s, 35 * s), SUBTITLE, font=reg, fill=MUTE, anchor="lm")
    d.line([24 * s, 62 * s, 616 * s, 62 * s], fill=LINE, width=max(1, s))
    # numbers over Install and Blocked, a line before Uninstall
    badge(d, 150, 89, 10, "1", num, s)
    badge(d, 330, 89, 10, "2", num, s)
    d.line([420 * s, 90 * s, 420 * s, 220 * s], fill=LINE, width=max(1, s))
    # the three steps
    y = 271
    for n, lines in STEPS:
        badge(d, 33, y, 9, n, num, s)
        for i, ln in enumerate(lines):
            d.text((52 * s, (y + i * 20) * s), ln, font=step, fill=INK, anchor="lm")
        y += 20 * len(lines) + 4 if len(lines) > 1 else 20
    d.text((24 * s, 393 * s), FOOT, font=small, fill=MUTE, anchor="lm")
    # dmajorsound logo top right: 36 px high, right edge at x = 616, top at y = 16
    if LOGO and os.path.isfile(LOGO):
        lg = Image.open(LOGO).convert("RGBA")
        h = 36 * s
        w = round(lg.width * h / lg.height)
        lg = lg.resize((w, h), Image.LANCZOS)
        im.paste(lg, (616 * s - w, 16 * s), lg)
    return im


if __name__ == "__main__":
    fonts, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    draw(fonts, 1).save(os.path.join(out, "background.png"))
    draw(fonts, 2).save(os.path.join(out, "background@2x.png"))
    print("wrote", out)

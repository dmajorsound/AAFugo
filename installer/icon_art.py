"""The AAFUGO icon = OLAAF's dark icon with the plane taking off: same plane, same sound rings, same clips.
Used for every installer image and the DMG window."""
import math
from PIL import Image, ImageDraw

DARK, EDGE = (32, 33, 37), (58, 59, 65)
WHITE, GREY = (255, 255, 255), (201, 204, 211)
RING, MINT = (99, 143, 190), (157, 235, 192)
OL_NOSE = (80, 46)
OL_PLANE = {"A": (32, 22), "C": (54, 24), "B": (53, 9)}
CLIPS = [[(46, 68), (58, 52), (86, 52), (98, 68)], [(22, 90), (22, 74), (52, 74), (62, 90)]]


def plane(deg, nose):
    th = math.radians(deg)
    o = {"N": nose}
    for k, (x, y) in OL_PLANE.items():
        dx, dy = x - OL_NOSE[0], y - OL_NOSE[1]
        o[k] = (nose[0] + dx * math.cos(th) - dy * math.sin(th), nose[1] + dx * math.sin(th) + dy * math.cos(th))
    return o


def draw(size, deg=0, nose=OL_NOSE):
    S = size * 4
    k = S / 120.0
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=28 * k, fill=DARK, outline=EDGE, width=max(1, round(k)))
    o = plane(deg, nose)
    P = lambda pts: [(x * k, y * k) for x, y in pts]
    d.polygon(P([o["N"], o["A"], o["C"]]), fill=WHITE)
    d.polygon(P([o["N"], o["C"], o["B"]]), fill=GREY)
    for c in CLIPS:
        d.polygon(P(c), fill=WHITE)
    cx, cy = o["N"]
    circ = lambda r: [(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k]
    d.ellipse(circ(4.5), fill=DARK)                      # knock-out around the dot
    d.ellipse(circ(6.75), outline=RING, width=round(2.25 * k))
    ov = Image.new("RGBA", (S, S), (0, 0, 0, 0))           # outer ring: the same blue at 55 %
    ImageDraw.Draw(ov).ellipse(circ(10.25), outline=RING + (140,), width=round(2.25 * k))
    base = Image.alpha_composite(base, ov)
    d = ImageDraw.Draw(base)
    d.ellipse(circ(2.75), fill=MINT)
    return base.resize((size, size), Image.LANCZOS)


DEG, NOSE = -55, (88, 24)  # 55 degrees climb, nose (with the rings) top right


def icon(size):
    return draw(size, DEG, NOSE)

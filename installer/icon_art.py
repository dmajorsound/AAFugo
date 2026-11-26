"""The AAFUGO icon, drawn the same way everywhere (installers, DMG window): dark like all dmajorsound
tool icons, OLAAF's two clips, a paper plane taking off - with the sound dot and its rings (as in
Ahh!) at the tip of the plane."""
from PIL import Image, ImageDraw

DARK = (32, 33, 37)
EDGE = (58, 59, 65)
BLUE = (76, 147, 220)
MINT = (157, 235, 192)
RING = (99, 143, 190)
NOSE = (76, 22)
SHAPES = [
    ([NOSE, (28, 46), (50, 44)], (255, 255, 255)),
    ([NOSE, (50, 44), (49, 59)], BLUE),
    ([(46, 68), (58, 52), (86, 52), (98, 68)], (255, 255, 255)),
    ([(22, 90), (22, 74), (52, 74), (62, 90)], (255, 255, 255)),
]
DOT_R = 4.2
RINGS = [(9.0, 2.3), (14.0, 2.3)]  # radius, line width (120-unit grid)
ARC = (262, 368)  # degrees, clockwise from 3 o'clock: the rings open up and to the right, where the plane flies


def icon(size):
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = S / 120.0
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=28 * k, fill=DARK, outline=EDGE, width=max(1, round(k)))
    for pts, col in SHAPES:
        d.polygon([(x * k, y * k) for x, y in pts], fill=col)
    cx, cy = NOSE
    for r, w in RINGS:
        d.arc([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], ARC[0], ARC[1], fill=RING, width=round(w * k))
    d.ellipse([(cx - DOT_R) * k, (cy - DOT_R) * k, (cx + DOT_R) * k, (cy + DOT_R) * k], fill=MINT)
    return im.resize((size, size), Image.LANCZOS)


def svg():
    import math
    def arc(r):
        a0, a1 = math.radians(ARC[0]), math.radians(ARC[1])
        x0, y0 = NOSE[0] + r * math.cos(a0), NOSE[1] + r * math.sin(a0)
        x1, y1 = NOSE[0] + r * math.cos(a1), NOSE[1] + r * math.sin(a1)
        return "M%.2f %.2f A%.1f %.1f 0 0 1 %.2f %.2f" % (x0, y0, r, r, x1, y1)
    hx = lambda c: "#%02X%02X%02X" % c
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">',
           '<rect x="0.5" y="0.5" width="119" height="119" rx="28" fill="%s" stroke="%s" stroke-width="1"/>' % (hx(DARK), hx(EDGE))]
    for pts, col in SHAPES:
        out.append('<path d="M%s Z" fill="%s"/>' % (" L".join("%g %g" % p for p in pts), hx(col)))
    for r, w in RINGS:
        out.append('<path d="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linecap="butt"/>' % (arc(r), hx(RING), w))
    out.append('<circle cx="%g" cy="%g" r="%g" fill="%s"/>' % (NOSE[0], NOSE[1], DOT_R, hx(MINT)))
    out.append('</svg>')
    return "".join(out)

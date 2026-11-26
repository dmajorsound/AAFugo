"""The AAFUGO icon, drawn the same way everywhere (installers, DMG window): dark like all dmajorsound
tool icons, OLAAF's two clips, a paper plane taking off with a blue facet."""
from PIL import Image, ImageDraw

DARK = (32, 33, 37)
EDGE = (58, 59, 65)
BLUE = (76, 147, 220)
SHAPES = [
    ([(88, 10), (40, 34), (62, 32)], (255, 255, 255)),
    ([(88, 10), (62, 32), (61, 47)], BLUE),
    ([(46, 68), (58, 52), (86, 52), (98, 68)], (255, 255, 255)),
    ([(22, 90), (22, 74), (52, 74), (62, 90)], (255, 255, 255)),
]


def icon(size):
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = S / 120.0
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=28 * k, fill=DARK, outline=EDGE, width=max(1, round(k)))
    for pts, col in SHAPES:
        d.polygon([(x * k, y * k) for x, y in pts], fill=col)
    return im.resize((size, size), Image.LANCZOS)

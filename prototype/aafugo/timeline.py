"""Timeline pages for the Flight Report: a drawn 'screenshot' of the session for the mixer.

One overview page with the whole session, then detail pages that split the session in time
(and, with many tracks, in rows) so every clip is wide enough to read: name, channels, gain,
fades, crossfades, rendered and muted items.
"""
import math

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable

INK = colors.HexColor("#1E1E1E")
MUTE = colors.HexColor("#5A5A5A")
LINE = colors.HexColor("#E2E2E2")
GRID = colors.HexColor("#EEEEEE")
BLUE = colors.HexColor("#4C93DC")
CLIP = colors.HexColor("#D6E6F7")
CLIP_ST = colors.HexColor("#C4DAF2")
EDGE = colors.HexColor("#4C93DC")
FOLD = colors.HexColor("#F2F6FB")
RENDER = colors.HexColor("#1E1E1E")
MUTED = colors.HexColor("#BBBBBB")
FADE = colors.HexColor("#2F6FB3")
DARK = False


def set_theme(dark):
    """Light (white page) or dark (OLAAF dark colors) for the timeline drawing."""
    global INK, MUTE, LINE, GRID, CLIP, CLIP_ST, EDGE, FOLD, RENDER, MUTED, FADE, DARK, NA_FILL
    DARK = dark
    if dark:
        INK, MUTE, LINE, GRID = (colors.HexColor(x) for x in ("#DCDCDC", "#989898", "#4A4A4A", "#3B3B3B"))
        CLIP, CLIP_ST, EDGE, FOLD = (colors.HexColor(x) for x in ("#37424E", "#3E4C5C", "#6BA4E0", "#2A2A2A"))
        RENDER, MUTED, FADE, NA_FILL = (colors.HexColor(x) for x in ("#FFFFFF", "#5A5A5A", "#8DB9E8", "#3B3B3B"))
    else:
        INK, MUTE, LINE, GRID = (colors.HexColor(x) for x in ("#1E1E1E", "#5A5A5A", "#E2E2E2", "#EEEEEE"))
        CLIP, CLIP_ST, EDGE, FOLD = (colors.HexColor(x) for x in ("#D6E6F7", "#C4DAF2", "#4C93DC", "#F2F6FB"))
        RENDER, MUTED, FADE, NA_FILL = (colors.HexColor(x) for x in ("#1E1E1E", "#BBBBBB", "#2F6FB3", "#F3F3F3"))


NA_FILL = colors.HexColor("#F3F3F3")
NAME_W = 44 * mm
RULER_H = 11 * mm
TITLE_H = 9 * mm


def _rows(session):
    """(track, kind, lanes) per row; kind folder|audio|empty|nonaudio."""
    rows = []
    na = {}
    for n in session.nonaudio:
        na.setdefault(n.track, []).append(n)
    for tr in session.tracks:
        if tr.is_folder:
            rows.append((tr, "folder", []))
            continue
        playing = [c for c in tr.clips if c.length * session.sample_rate >= 1]
        if not playing and tr.name in na:
            rows.append((tr, "nonaudio", na[tr.name]))
            continue
        if not playing:
            rows.append((tr, "empty", []))
            continue
        # stacked items get their own lane inside the row
        lanes = []
        for c in sorted(playing, key=lambda c: c.position):
            for lane in lanes:
                last = lane[-1]
                if c.position >= last.end - 1e-9 or (c.end > last.end and (last.fade_out > 0 or c.fade_in > 0)):
                    lane.append(c)
                    break
            else:
                lanes.append([c])
        rows.append((tr, "audio", lanes))
    return rows


def _row_h(kind, nlanes, base):
    if kind in ("folder", "empty"):
        return 4.2 * mm
    return base * max(1, nlanes)


def _mix(hexcol, other, t):
    a = colors.HexColor(hexcol)
    return colors.Color(a.red * (1 - t) + other[0] * t, a.green * (1 - t) + other[1] * t, a.blue * (1 - t) + other[2] * t)


def _fit(text, font, size, width):
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…" if text else ""


def _db(g):
    return "%+.1f dB" % (20 * math.log10(g)) if g > 0 else "-inf"


class TimelinePage(Flowable):
    def __init__(self, session, rows, t0, t1, width, height, title, detail=True):
        super().__init__()
        self.s, self.rows, self.t0, self.t1 = session, rows, t0, t1
        self.width, self.height, self.title, self.detail = width, height, title, detail

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        s = self.s
        W, H = self.width, self.height
        x0 = NAME_W
        tw = W - NAME_W
        span = max(self.t1 - self.t0, 1e-6)
        X = lambda t: x0 + (t - self.t0) / span * tw
        # title
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(INK)
        c.drawString(0, H - 5 * mm, self.title)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUTE)
        c.drawRightString(W, H - 5 * mm, "%s  –  %s" % (s.tc(self.t0), s.tc(self.t1)))
        top = H - TITLE_H
        # ruler
        ry = top - RULER_H
        c.setStrokeColor(LINE)
        c.line(x0, ry, W, ry)
        pps = tw / span  # points per second
        fps = s.fps or 25
        steps = [1 / fps, 2 / fps, 5 / fps, 10 / fps, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
        major = next((st for st in steps if st * pps >= 42), steps[-1])
        minor = next((st for st in steps if st * pps >= 6), major)
        t = math.floor(self.t0 / minor) * minor
        c.setFont("Helvetica", 6)
        while t <= self.t1 + 1e-9:
            if t >= self.t0 - 1e-9:
                xx = X(t)
                is_major = abs(round(t / major) * major - t) < 1e-6
                c.setStrokeColor(MUTE if is_major else LINE)
                c.line(xx, ry, xx, ry + (3.5 * mm if is_major else 1.6 * mm))
                if is_major:
                    c.setFillColor(MUTE)
                    c.drawString(xx + 1.2, ry + 4.4 * mm, s.tc(t))
            t += minor
        # rows
        base = getattr(self, "row_base", 7 * mm)
        y = ry
        for tr, kind, lanes in self.rows:
            h = _row_h(kind, len(lanes) if kind == "audio" else 1, base)
            y -= h
            if kind == "folder":
                c.setFillColor(FOLD)
                c.rect(0, y, W, h, stroke=0, fill=1)
            c.setStrokeColor(LINE)
            c.line(0, y, W, y)
            # vertical grid on major ticks
            # name column
            c.setFillColor(INK)
            fnt = "Helvetica-Bold" if kind == "folder" else "Helvetica"
            c.setFont(fnt, 7 if kind != "folder" else 6.8)
            indent = 3.2 * mm * tr.depth
            if tr.color:
                c.setFillColor(colors.HexColor(tr.color))
                c.rect(NAME_W - 3 * mm, y + 1, 2 * mm, h - 2, stroke=0, fill=1)
                c.setFillColor(INK)
            label = tr.name + ("  (folder)" if kind == "folder" else "")
            c.drawString(1.5 + indent, y + h / 2 - 2.3, _fit(label, fnt, 7, NAME_W - indent - 4 - 3.5 * mm))
            if kind == "nonaudio":
                for n in lanes:
                    a, b = max(n.position, self.t0), min(n.position + n.length, self.t1)
                    if b <= a:
                        continue
                    c.setFillColor(NA_FILL)
                    c.setStrokeColor(MUTED)
                    c.setDash(2, 2)
                    c.rect(X(a), y + 1, X(b) - X(a), h - 2, stroke=1, fill=1)
                    c.setDash()
                    c.setFillColor(MUTE)
                    c.setFont("Helvetica", 6)
                    c.drawString(X(a) + 2, y + h / 2 - 2, _fit("%s – %s (sorted out)" % (n.kind, n.name), "Helvetica", 6, X(b) - X(a) - 4))
                continue
            if kind != "audio":
                continue
            lh = h / len(lanes)
            for li, lane in enumerate(lanes):
                ly = y + h - (li + 1) * lh
                for clip in lane:
                    self._clip(c, clip, X, ly, lh)
        # outer frame of the timeline area
        c.setStrokeColor(LINE)
        c.line(x0, y, x0, ry)

    def _clip(self, c, cl, X, y, h):
        a, b = cl.position, cl.end
        if b <= self.t0 or a >= self.t1:
            return
        xa, xb = X(max(a, self.t0)), X(min(b, self.t1))
        pad = 0.8
        top, bot = y + h - pad, y + pad
        st = cl.source and cl.source.channels == 2
        if cl.color and not cl.muted:
            fill = _mix(cl.color, (0.2, 0.2, 0.2), 0.55) if DARK else _mix(cl.color, (1, 1, 1), 0.45)
            edge = _mix(cl.color, (1, 1, 1), 0.2) if DARK else _mix(cl.color, (0, 0, 0), 0.45)
        else:
            fill = MUTED if cl.muted else (CLIP_ST if st else CLIP)
            edge = MUTED if cl.muted else EDGE
        c.saveState()
        c.setFillColor(fill)
        c.setFillAlpha(0.85)
        c.setStrokeColor(RENDER if cl.needs_render and not cl.muted else edge)
        c.setLineWidth(1.3 if cl.needs_render else 0.6)
        if cl.muted:
            c.setDash(2, 1.5)
        c.rect(xa, bot, xb - xa, top - bot, stroke=1, fill=1)
        c.setDash()
        c.setFillAlpha(1)
        # fades: the line the level follows, from silence to full
        c.setStrokeColor((_mix(cl.color, (1, 1, 1), 0.5) if DARK else _mix(cl.color, (0, 0, 0), 0.6))
                         if cl.color and not cl.muted else FADE)
        c.setLineWidth(0.6)
        if cl.fade_in > 0 and a >= self.t0:
            c.line(X(a), bot, X(min(a + cl.fade_in, self.t1)), top)
        if cl.fade_out > 0 and b <= self.t1:
            c.line(X(max(b - cl.fade_out, self.t0)), top, X(b), bot)
        # text: name, then channels / gain on the right
        w = xb - xa - 3
        if w > 6 and self.detail:
            size = 5.8 if h > 5.5 * mm else 5
            right = []
            if st:
                right.append("ST")
            if abs(cl.gain - 1) > 1e-6:
                right.append(_db(cl.gain))
            if cl.needs_render:
                right.append("R")
            rt = "  ".join(right)
            rw = stringWidth(rt, "Helvetica-Bold", size) + 3 if rt else 0
            c.setFillColor(INK)
            c.setFont("Helvetica", size)
            name = cl.name.rsplit(".", 1)[0] if cl.name.lower().endswith((".wav", ".aif", ".aiff")) else cl.name
            if rw and w - rw > 18:
                c.drawString(xa + 1.6, (top + bot) / 2 - size * 0.35, _fit(name, "Helvetica", size, w - rw))
                c.setFont("Helvetica-Bold", size)
                c.setFillColor(INK)
                c.drawRightString(xb - 1.4, (top + bot) / 2 - size * 0.35, rt)
            else:
                c.drawString(xa + 1.6, (top + bot) / 2 - size * 0.35, _fit(name, "Helvetica", size, w))
        c.restoreState()


def _legend(width):
    class L(Flowable):
        def wrap(self, aw, ah):
            return width, 7 * mm

        def draw(self):
            c = self.canv
            x = 0
            items = [(CLIP, EDGE, "clip in its REAPER color", False), (CLIP, RENDER, "black frame + R = rendered on export", False),
                     (MUTED, MUTED, "muted - stays home", True)]
            c.setFont("Helvetica", 6.8)
            for f, e, t, dash in items:
                c.setFillColor(f)
                c.setStrokeColor(e)
                if dash:
                    c.setDash(2, 1.5)
                c.rect(x, 2.2 * mm, 7 * mm, 3 * mm, stroke=1, fill=1)
                c.setDash()
                c.setFillColor(MUTE)
                c.drawString(x + 8.5 * mm, 2.9 * mm, t)
                x += 9 * mm + stringWidth(t, "Helvetica", 6.8) + 6 * mm
            c.setStrokeColor(FADE)
            c.line(x, 2.2 * mm, x + 7 * mm, 5.2 * mm)
            c.setFillColor(MUTE)
            c.drawString(x + 8.5 * mm, 2.9 * mm, "fade / crossfade")
            x += 9 * mm + stringWidth("fade / crossfade", "Helvetica", 6.8) + 6 * mm
            c.drawString(x, 2.9 * mm, "ST = stereo file    dB = clip gain")
    return L()


def timeline_flowables(session, width, height, min_sec_width=30 * mm, row_base=5.0 * mm, min_row=4.2 * mm):
    from reportlab.platypus import PageBreak
    rows = _rows(session)
    ends = [c.end for t in session.tracks for c in t.clips] + [n.position + n.length for n in session.nonaudio]
    t_end = max(ends) if ends else 1.0
    t_start = min([c.position for t in session.tracks for c in t.clips] + [0.0])
    usable_h = height - TITLE_H - RULER_H - 13 * mm
    out = []

    def fit_rows(rs, base):
        total = sum(_row_h(k, len(l) if k == "audio" else 1, base) for _, k, l in rs)
        return total

    # overview: everything on one page, rows squeezed to fit
    over_base = row_base
    while fit_rows(rows, over_base) > usable_h and over_base > 2.2 * mm:
        over_base -= 0.2 * mm
    pg = TimelinePage(session, rows, t_start, t_end, width, height - 12 * mm, "Session overview", detail=over_base > 4.5 * mm)
    pg.row_base = over_base
    out += [_legend(width), pg]
    # detail pages: windows of time, and chunks of rows if needed
    # zoom so that most clips (4 of 5) are at least ~28 mm wide and their names readable
    lens = sorted(c.length for t in session.tracks for c in t.clips if c.length * session.sample_rate >= 1)
    if lens:
        p20 = lens[int(len(lens) * 0.2)]
        min_sec_width = min(max(min_sec_width, 12 * mm / max(p20, 1e-3)), 200 * mm)
    sec = (width - NAME_W) / min_sec_width
    n_t = max(1, int(math.ceil((t_end - t_start) / sec - 1e-9)))
    sec = (t_end - t_start) / n_t
    chunks, cur, h = [], [], 0
    for r in rows:
        rh = _row_h(r[1], len(r[2]) if r[1] == "audio" else 1, row_base)
        if cur and h + rh > usable_h:
            chunks.append(cur)
            cur, h = [], 0
        cur.append(r)
        h += rh
    if cur:
        chunks.append(cur)
    total = n_t * len(chunks)
    k = 0
    for ci, ch in enumerate(chunks):
        for i in range(n_t):
            k += 1
            out.append(PageBreak())
            title = "Session detail %d / %d" % (k, total)
            if len(chunks) > 1:
                title += "  –  tracks %d of %d" % (ci + 1, len(chunks))
            pg = TimelinePage(session, ch, t_start + i * sec, t_start + (i + 1) * sec, width, height, title)
            pg.row_base = row_base
            out.append(pg)
    return out

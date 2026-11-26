"""AAFUGO prototype: the Flight Report (handover sheet) as PDF.

What the mixer needs next to the AAF: start TC, rates, the Pre-Flight findings, the track tree
with folders, and every plugin on tracks, folders and master with its settings - plugins never
travel in an AAF.
"""
import datetime
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

BLUE = colors.HexColor("#4C93DC")
INK = colors.HexColor("#1E1E1E")
MUTE = colors.HexColor("#5A5A5A")
LINE = colors.HexColor("#E2E2E2")
DOT = {"problem": colors.HexColor("#D64541"), "warning": colors.HexColor("#E0A526"),
       "note": BLUE, "ok": colors.HexColor("#3E9C5A")}
TARGET = {"pt": ("PTX", "Pro Tools"), "nuendo": ("NUE", "Nuendo/Cubase"), "logic": ("LGC", "Logic"),
          "resolve": ("DVR", "Resolve/Fairlight"), "dawproject": ("NUE", "Nuendo/Cubase"),
          "sesx": ("AUD", "Audition"), "fcpxml": ("LGC", "Logic")}

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, textColor=INK, leading=22)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=8.5, textColor=MUTE, leading=12, spaceBefore=10,
                    spaceAfter=4)
TX = ParagraphStyle("tx", fontName="Helvetica", fontSize=9, textColor=INK, leading=12)
SM = ParagraphStyle("sm", fontName="Helvetica", fontSize=8, textColor=MUTE, leading=10.5)
MONO = ParagraphStyle("mono", fontName="Courier", fontSize=8, textColor=INK, leading=10.5)


def _p(t, st=None):
    return Paragraph(escape(str(t)), st or TX)


def _fx_text(f):
    parts = [f["name"]]
    if f["bypassed"]:
        parts.append("(bypassed)")
    if f["offline"]:
        parts.append("(offline)")
    if f.get("preset"):
        parts.append("preset: " + f["preset"])
    if f.get("params"):
        parts.append("; ".join("%s %s" % (k, v) for k, v in f["params"]))
    elif f.get("values"):
        parts.append("sliders: " + " ".join(f["values"]))
    return " ".join(parts)


def channels_text(tr):
    """'mono', 'stereo', '2 stereo, 3 mono' ... from the files of the playing clips."""
    cnt = {}
    for c in tr.clips:
        if c.muted or not c.source or not c.source.channels:
            continue
        k = {1: "mono", 2: "stereo"}.get(c.source.channels, "%d ch" % c.source.channels)
        cnt[k] = cnt.get(k, 0) + 1
    if not cnt:
        return "-"
    if len(cnt) == 1:
        return next(iter(cnt))
    return ", ".join("%d %s" % (v, k) for k, v in sorted(cnt.items(), key=lambda x: -x[1]))


def _theme(dark):
    global INK, MUTE, LINE, H1, H2, TX, SM, MONO, HEAD, FOLDROW, PAGE
    if dark:
        INK, MUTE, LINE = colors.HexColor("#DCDCDC"), colors.HexColor("#989898"), colors.HexColor("#4A4A4A")
        HEAD, FOLDROW, PAGE = colors.HexColor("#2A2A2A"), colors.HexColor("#2A2A2A"), colors.HexColor("#333333")
    else:
        INK, MUTE, LINE = colors.HexColor("#1E1E1E"), colors.HexColor("#5A5A5A"), colors.HexColor("#E2E2E2")
        HEAD, FOLDROW, PAGE = colors.HexColor("#F2F6FB"), colors.HexColor("#F2F6FB"), None
    H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, textColor=INK, leading=22)
    H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=8.5, textColor=MUTE, leading=12, spaceBefore=10, spaceAfter=4)
    TX = ParagraphStyle("tx", fontName="Helvetica", fontSize=9, textColor=INK, leading=12)
    SM = ParagraphStyle("sm", fontName="Helvetica", fontSize=8, textColor=MUTE, leading=10.5)
    MONO = ParagraphStyle("mono", fontName="Courier", fontSize=8, textColor=INK, leading=10.5)


def write(session, out_path, target="pt", export_file="", logo=None, version="0.1", dark=False):
    _theme(dark)
    from . import timeline as _tl
    _tl.set_theme(dark)
    blue = "#6BA4E0" if dark else "#4C93DC"
    code, label = TARGET.get(target, ("???", target))
    doc = BaseDocTemplate(out_path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=20 * mm, title="AAFUGO Flight Report - %s" % session.name)
    W = A4[0] - 36 * mm
    E = []
    E.append(Paragraph('<font color="%s">AAF</font>UGO <font size="11" color="%s">Flight Report</font>'
                       % (blue, MUTE.hexval().replace("0x", "#")), H1))
    E.append(Spacer(1, 6))
    # boarding-pass style header
    hdr = [[_p("FROM", SM), _p("TO", SM), _p("PASSENGER", SM), _p("GATE - START TC", SM), _p("SEAT", SM)],
           [_p("RPR  Reaper"), _p("%s  %s" % (code, label)), _p(session.name), _p(session.tc(0)),
            _p("%d Hz - %g fps" % (session.sample_rate, session.fps))]]
    t = Table(hdr, colWidths=[W * 0.16, W * 0.22, W * 0.26, W * 0.17, W * 0.19])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("BACKGROUND", (0, 0), (-1, 0), HEAD),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    E.append(t)
    E.append(Spacer(1, 3))
    E.append(_p("Export file: %s    -    %s" % (export_file or "-", datetime.date.today().isoformat()), SM))

    E.append(_p("SECURITY CHECK (PRE-FLIGHT)", H2))
    rows = []
    for f in session.findings:
        rows.append(["", _p(f.title), _p(f.detail, SM)])
    t = Table(rows, colWidths=[5 * mm, W * 0.42, W * 0.58 - 5 * mm])
    st = [("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i, f in enumerate(session.findings):
        st.append(("BACKGROUND", (0, i), (0, i), DOT[f.level]))
    t.setStyle(TableStyle(st + [("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 0)]))
    E.append(t)

    E.append(_p("TRACKS, FOLDERS AND PLUGINS", H2))
    E.append(_p("Folders carry no audio. Their plugins process every track inside - recreate them on a bus "
                "or VCA in the mix. Plugins never travel in an AAF.", SM))
    if target == "dawproject":
        E.append(_p("In this DAWproject, folders arrive as group tracks and VST2 plugins travel with their "
                    "settings (the plugin must be installed on the other side). JS plugins exist only in REAPER.", SM))
    E.append(Spacer(1, 4))
    rows = [[_p("TRACK", SM), _p("CLIPS", SM), _p("CHANNELS", SM), _p("PLUGINS AND SETTINGS", SM)]]
    st = [("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for tr in session.tracks:
        n = len([c for c in tr.clips if not c.muted])
        name = ("&nbsp;" * 4 * tr.depth) + ("<b>%s</b> <font color='#989898'>(folder)</font>" % escape(tr.name)
                                             if tr.is_folder else escape(tr.name))
        fx = "<br/>".join(escape(_fx_text(f)) for f in tr.fx) or "<font color='#9A9A9A'>-</font>"
        rows.append([Paragraph(name, TX), _p(n if n else "-"), _p(channels_text(tr), SM), Paragraph(fx, MONO)])
        if tr.is_folder:
            st.append(("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), FOLDROW))
    rows.append([Paragraph("<b>Master</b>", TX), _p("-"), _p("-"),
                 Paragraph("<br/>".join(escape(_fx_text(f)) for f in session.master_fx) or "-", MONO)])
    t = Table(rows, colWidths=[W * 0.29, W * 0.09, W * 0.15, W * 0.47], repeatRows=1)
    t.setStyle(TableStyle(st))
    E.append(t)

    rnd = [(tr, c) for tr in session.tracks for c in tr.clips if c.needs_render and not c.muted]
    if rnd:
        E.append(_p("RENDERED ITEMS", H2))
        rows = [[_p(tr.name), _p(session.tc(c.position), MONO), _p(c.name, SM), _p(", ".join(c.needs_render), SM)]
                for tr, c in rnd]
        t = Table(rows, colWidths=[W * 0.2, W * 0.16, W * 0.44, W * 0.2])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        E.append(t)
    if session.nonaudio:
        E.append(_p("SORTED OUT (NON-AUDIO, NOT IN THE EXPORT)", H2))
        rows = [[_p(n.kind), _p(n.track), _p(session.tc(n.position), MONO), _p(n.name, SM)] for n in session.nonaudio]
        t = Table(rows, colWidths=[W * 0.14, W * 0.26, W * 0.16, W * 0.44])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]))
        E.append(t)

    def footer(canvas, d):
        canvas.saveState()
        if PAGE is not None:
            canvas.setFillColor(PAGE)
            canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        y = 12 * mm
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, y + 5 * mm, A4[0] - 18 * mm, y + 5 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTE)
        canvas.drawString(18 * mm, y, "V %s - developed with AI assistance" % version)
        x = A4[0] - 18 * mm
        if logo and os.path.isfile(logo):
            canvas.drawImage(logo, x - 5.6 * mm, y - 1.2 * mm, width=5.6 * mm, height=3.8 * mm, mask="auto")
            x -= 7.5 * mm
        canvas.drawRightString(x, y, "dmajorsound.com")
        canvas.drawCentredString(A4[0] / 2, y, "page %d" % d.page)
        canvas.restoreState()

    from reportlab.platypus import NextPageTemplate, PageTemplate, Frame, PageBreak
    from .timeline import timeline_flowables
    land = (A4[1], A4[0])
    portrait_frame = Frame(18 * mm, 20 * mm, A4[0] - 36 * mm, A4[1] - 36 * mm, id="p")
    land_frame = Frame(12 * mm, 18 * mm, land[0] - 24 * mm, land[1] - 28 * mm, id="l")

    def footer_land(canvas, d):
        canvas.saveState()
        if PAGE is not None:
            canvas.setFillColor(PAGE)
            canvas.rect(0, 0, land[0], land[1], stroke=0, fill=1)
        y = 9 * mm
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(12 * mm, y + 5 * mm, land[0] - 12 * mm, y + 5 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTE)
        canvas.drawString(12 * mm, y, "V %s - developed with AI assistance" % version)
        x = land[0] - 12 * mm
        if logo and os.path.isfile(logo):
            canvas.drawImage(logo, x - 5.6 * mm, y - 1.2 * mm, width=5.6 * mm, height=3.8 * mm, mask="auto")
            x -= 7.5 * mm
        canvas.drawRightString(x, y, "dmajorsound.com")
        canvas.drawCentredString(land[0] / 2, y, "page %d" % d.page)
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate("portrait", [portrait_frame], onPage=footer, pagesize=A4),
                          PageTemplate("landscape", [land_frame], onPage=footer_land, pagesize=land)])
    E.append(NextPageTemplate("landscape"))
    E.append(PageBreak())
    E += timeline_flowables(session, land[0] - 24 * mm - 13, land[1] - 28 * mm - 13)
    doc.build(E)
    return {"pages": "ok"}

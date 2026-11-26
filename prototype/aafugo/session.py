"""AAFUGO prototype: read a REAPER project (.rpp) into a simple session model.

The model is what every writer (AAF, DAWproject, Audition, ...) works from:
  Session -> tracks -> clips (audio only), plus the non-audio items that were sorted out and
  the Pre-Flight findings.
Times are in seconds of REAPER project time (0 = project start); `offset` is REAPER's
project start offset (PROJOFFS), so the timecode of a position is offset + position.
"""
import os
import shlex
import struct

AUDIO_SOURCES = {"WAVE", "FLAC", "MP3", "VORBIS", "OPUS", "WAVPACK"}
NONAUDIO_KIND = {"MIDI": "MIDI", "VIDEO": "VIDEO", "RPP_PROJECT": "SUBPROJECT", "CLICK": "GENERATOR",
                 "EMPTY": "NOTES", "": "NOTES"}


# ------------------------------------------------------------------ RPP text -> tree
class Node:
    __slots__ = ("tag", "args", "lines", "children")

    def __init__(self, tag, args):
        self.tag, self.args, self.lines, self.children = tag, args, [], []

    def first(self, key):
        for ln in self.lines:
            if ln and ln[0] == key:
                return ln[1:]
        return None

    def child(self, tag):
        for c in self.children:
            if c.tag == tag:
                return c
        return None


def _split(line):
    try:
        return shlex.split(line, posix=True)
    except ValueError:
        return line.split()


def parse_rpp(text):
    root = Node("ROOT", [])
    stack = [root]
    # each line is either "<TAG args", ">" or "KEY values"; item takes are flat lines inside ITEM
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("<"):
            parts = _split(s[1:])
            n = Node(parts[0] if parts else "", parts[1:])
            stack[-1].children.append(n)
            stack[-1].lines.append(("<child>", n))  # keep order of lines and children
            stack.append(n)
        elif s == ">":
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].lines.append(tuple(_split(s)))
    return root.children[0] if root.children else root


# ------------------------------------------------------------------ media
class Source:
    def __init__(self, path):
        self.path = path
        self.exists = os.path.isfile(path)
        self.sample_rate = None
        self.channels = None
        self.frames = None
        self.bits = None
        self.time_ref = 0  # BWF time reference, samples since midnight
        self.is_wav = path.lower().endswith((".wav", ".bwf"))
        if self.exists and self.is_wav:
            self._read_wav()

    @property
    def duration(self):
        return self.frames / self.sample_rate if self.frames and self.sample_rate else None

    def _read_wav(self):
        with open(self.path, "rb") as f:
            hdr = f.read(12)
            if hdr[:4] not in (b"RIFF", b"RF64") or hdr[8:12] != b"WAVE":
                return
            data_size = None
            while True:
                ch = f.read(8)
                if len(ch) < 8:
                    break
                cid, size = ch[:4], struct.unpack("<I", ch[4:])[0]
                if cid == b"fmt ":
                    d = f.read(size)
                    _, self.channels, self.sample_rate, _, block, self.bits = struct.unpack("<HHIIHH", d[:16])
                elif cid == b"bext":
                    d = f.read(size)
                    if len(d) >= 346:
                        self.time_ref = struct.unpack("<Q", d[338:346])[0]
                elif cid == b"data":
                    data_size = size
                    f.seek(size + (size & 1), 1)
                else:
                    f.seek(size + (size & 1), 1)
            if data_size is not None and self.channels and self.bits:
                self.frames = data_size // (self.channels * self.bits // 8)


# ------------------------------------------------------------------ model
class Clip:
    def __init__(self):
        self.name = ""
        self.position = 0.0     # s, project time
        self.length = 0.0       # s on the timeline
        self.offset = 0.0       # s into the source (SOFFS)
        self.fade_in = 0.0
        self.fade_out = 0.0
        self.fade_in_shape = 0
        self.fade_out_shape = 0
        self.gain = 1.0         # linear (item volume x take volume)
        self.source = None      # Source
        self.playrate = 1.0
        self.needs_render = []  # reasons: "take FX", "playrate", "pitch", "stretch markers"
        self.takes = 1
        self.muted = False
        self.color = None       # item color, else the track's

    @property
    def end(self):
        return self.position + self.length


class Track:
    def __init__(self, name, index):
        self.name, self.index = name, index
        self.clips = []
        self.channels = 1
        self.fx = []            # [{"name", "type", "bypassed", "offline", "preset", "values"}]
        self.is_folder = False
        self.depth = 0          # folder nesting level (0 = top)
        self.color = None       # "#RRGGBB" or None (REAPER default)
        self.parent = None      # name of the folder track it sits in


PLUGIN_TAGS = {"VST", "VST3", "AU", "JS", "CLAP", "DX", "LV2", "VIDEO_EFFECT"}


def parse_fx(chain):
    """Plugins of an FXCHAIN / MASTERFXLIST node, in order, with bypass/offline and preset."""
    out, pending = [], (False, False)
    for ln in chain.lines:
        if not ln:
            continue
        if ln[0] == "BYPASS":
            pending = (len(ln) > 1 and ln[1] == "1", len(ln) > 2 and ln[2] == "1")
        elif ln[0] == "<child>" and ln[1].tag in PLUGIN_TAGS:
            n = ln[1]
            name = n.args[0] if n.args else n.tag
            if n.tag == "JS":
                name = "JS: " + name
            values = []
            if n.tag == "JS" and n.lines:
                values = [v for v in n.lines[0] if v != "-"]
            out.append({"name": name, "type": n.tag, "bypassed": pending[0], "offline": pending[1],
                        "preset": "", "values": values, "args": list(n.args),
                        "state": [ln[0] for ln in n.lines if ln and ln[0] != "<child>"]})
            pending = (False, False)
        elif ln[0] == "PRESETNAME" and out:
            out[-1]["preset"] = " ".join(ln[1:])
    return out


def lanes(track, sample_rate):
    """Split a track's playing clips into lanes that a single AAF sequence can hold.

    Clips that overlap the previous one like a crossfade (the later one ends later and one of
    them has a fade) stay in the lane; stacked / layered clips move to the next free lane.
    Clips shorter than one sample are left out.
    """
    out = []
    for c in track.clips:
        if c.muted or not c.source or not c.source.exists or not c.source.frames:
            continue
        if int(round(c.length * sample_rate)) < 1:
            continue
        for lane in out:
            last = lane[-1]
            if c.position >= last.end - 1e-9:
                lane.append(c)
                break
            if c.end > last.end and (last.fade_out > 0 or c.fade_in > 0) and \
                    (len(lane) < 2 or c.position >= lane[-2].end):
                lane.append(c)
                break
        else:
            out.append([c])
    return out


class NonAudio:
    def __init__(self, kind, track, position, length, name):
        self.kind, self.track, self.position, self.length, self.name = kind, track, position, length, name


class Finding:
    """One Pre-Flight line: level is problem | warning | note | ok."""

    def __init__(self, level, title, detail="", where=None):
        self.level, self.title, self.detail, self.where = level, title, detail, where

    def __repr__(self):
        return "[%s] %s%s" % (self.level, self.title, (" - " + self.detail) if self.detail else "")


class Session:
    def __init__(self):
        self.path = ""
        self.name = ""
        self.sample_rate = 48000
        self.fps = 25.0
        self.offset = 0.0
        self.tracks = []
        self.nonaudio = []
        self.findings = []
        self.videos = []        # (path, position or None)
        self.master_fx = []

    def tc(self, seconds):
        """Timecode string of a project-time position."""
        t = self.offset + seconds
        fps = int(round(self.fps))
        fr = int(round(t * self.fps))
        h, fr = divmod(fr, 3600 * fps)
        m, fr = divmod(fr, 60 * fps)
        s, fr = divmod(fr, fps)
        return "%02d:%02d:%02d:%02d" % (h, m, s, fr)


def native_color(v, rgb_order):
    """REAPER custom color (native | 0x1000000) -> '#RRGGBB'. On macOS/Linux REAPER (SWELL) keeps
    0xRRGGBB, on Windows 0xBBGGRR. 0 / no flag = default color."""
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        return None
    if not v & 0x1000000:
        return None
    v &= 0xFFFFFF
    r, g, b = ((v >> 16) & 255, (v >> 8) & 255, v & 255) if rgb_order else (v & 255, (v >> 8) & 255, (v >> 16) & 255)
    return "#%02X%02X%02X" % (r, g, b)


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _takes(item):
    """Split an ITEM's lines into takes. Lines before the first TAKE belong to take 1."""
    takes, cur, selected = [], {"lines": [], "children": []}, 0
    for ln in item.lines:
        if ln and ln[0] == "<child>":
            cur["children"].append(ln[1])
        elif ln and ln[0] == "TAKE":
            takes.append(cur)
            cur = {"lines": [], "children": []}
            if len(ln) > 1 and ln[1] == "SEL":
                selected = len(takes)
        else:
            cur["lines"].append(ln)
    takes.append(cur)
    return takes, selected


def _get(lines, key):
    for ln in lines:
        if ln and ln[0] == key:
            return ln[1:]
    return None


ITEM_KEYS = {"POSITION", "LENGTH", "FADEIN", "FADEOUT", "MUTE", "LOOP", "SNAPOFFS", "SEL", "ALLTAKES", "IGUID",
             "IID", "GROUP"}


def load(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        root = parse_rpp(f.read())
    s = Session()
    s.path = path
    s.name = os.path.splitext(os.path.basename(path))[0]
    base = os.path.dirname(os.path.abspath(path))
    sr = root.first("SAMPLERATE")
    if sr:
        s.sample_rate = int(_num(sr[0], 48000)) or 48000
    po = root.first("PROJOFFS")
    if po:
        s.offset = _num(po[0])
    tm = root.first("TIMEMODE")
    if tm and len(tm) > 3 and _num(tm[3]) > 0:
        s.fps = _num(tm[3])
    else:
        ss = root.first("SMPTESYNC")
        if ss and len(ss) > 1 and _num(ss[1]) > 0:
            s.fps = _num(ss[1])

    plat = (root.args[1] if len(root.args) > 1 else "").lower()
    rgb_order = False  # the .rpp keeps colors as 0xBBGGRR on every platform (checked with Bernd's macOS session)
    mfx = root.child("MASTERFXLIST")
    if mfx:
        s.master_fx = parse_fx(mfx)
    sources = {}
    depth, parents = 0, []
    for ti, tn in enumerate([c for c in root.children if c.tag == "TRACK"]):
        name = (tn.first("NAME") or ["Track %d" % (ti + 1)])[0]
        tr = Track(name, ti)
        pc = tn.first("PEAKCOL")
        tr.color = native_color(pc[0], rgb_order) if pc else None
        fxc = tn.child("FXCHAIN")
        if fxc:
            tr.fx = parse_fx(fxc)
        tr.depth = depth
        tr.parent = parents[-1] if parents else None
        bus = tn.first("ISBUS") or ["0", "0"]
        if bus[0] == "1":  # folder start
            tr.is_folder = True
            depth += 1
            parents.append(name)
        elif bus[0] == "2":  # last track in folder(s): second value is the depth change
            for _ in range(min(-int(_num(bus[1] if len(bus) > 1 else -1)), len(parents))):
                depth -= 1
                parents.pop()
        for it in [c for c in tn.children if c.tag == "ITEM"]:
            takes, sel = _takes(it)
            item_lines = takes[0]["lines"]
            pos = _num((_get(item_lines, "POSITION") or [0])[0])
            length = _num((_get(item_lines, "LENGTH") or [0])[0])
            take = takes[sel]
            tl, tc = take["lines"], take["children"]
            src = next((c for c in tc if c.tag == "SOURCE"), None)
            kind = src.args[0] if src and src.args else ""
            name_t = (_get(tl, "NAME") or _get(item_lines, "NAME") or [""])[0]
            # a SECTION (reversed / section) wraps the real source
            if kind == "SECTION" and src.child("SOURCE"):
                src = src.child("SOURCE")
                kind = src.args[0] if src.args else ""
            notes = it.child("NOTES")
            if kind not in AUDIO_SOURCES:
                nk = NONAUDIO_KIND.get(kind, "OTHER")
                s.nonaudio.append(NonAudio(nk, name, pos, length, name_t or ("notes" if notes else kind.lower())))
                if kind == "VIDEO" and src is not None:
                    vf = (src.first("FILE") or [""])[0]
                    s.videos.append((os.path.join(base, vf) if vf and not os.path.isabs(vf) else vf, pos))
                continue
            c = Clip()
            c.name = name_t or "clip"
            c.position, c.length = pos, length
            c.offset = _num((_get(tl, "SOFFS") or [0])[0])
            fi = _get(item_lines, "FADEIN") or [0, 0]
            fo = _get(item_lines, "FADEOUT") or [0, 0]
            # FADEIN shape len autolen ...: an auto-crossfade length (> 0) wins over the manual length
            eff = lambda v: (_num(v[2]) if len(v) > 2 and _num(v[2]) > 0 else (_num(v[1]) if len(v) > 1 else 0.0))
            c.fade_in_shape, c.fade_in = int(_num(fi[0])), eff(fi)
            c.fade_out_shape, c.fade_out = int(_num(fo[0])), eff(fo)
            # REAPER: "auto" fades of shared overlaps are in the 4th field (len) when set; keep it simple here
            vp = _get(tl, "VOLPAN")
            c.gain = _num(vp[0], 1.0) if vp else 1.0
            mute = _get(item_lines, "MUTE")
            c.muted = bool(mute and _num(mute[0]) == 1)
            pr = _get(tl, "PLAYRATE")
            if pr:
                c.playrate = _num(pr[0], 1.0)
                if abs(c.playrate - 1.0) > 1e-9:
                    c.needs_render.append("playrate")
                if len(pr) > 2 and abs(_num(pr[2])) > 1e-9:
                    c.needs_render.append("pitch")
            if any(x.tag == "TAKEFX" for x in tc):
                c.needs_render.append("take FX")
            if _get(tl, "SM"):
                c.needs_render.append("stretch markers")
            c.takes = len(takes)
            ic = _get(item_lines, "COLOR")
            c.color = (native_color(ic[0], rgb_order) if ic else None) or tr.color
            f = (src.first("FILE") or [""])[0]
            full = f if os.path.isabs(f) else os.path.join(base, f)
            if not os.path.isfile(full):
                # moved project: look next to the .rpp and in its media folders, like REAPER does
                bn = os.path.basename(f.replace("\\", "/"))
                for d in ("", "media", "Media", "Audio", "audio"):
                    cand = os.path.join(base, d, bn)
                    if os.path.isfile(cand):
                        full = cand
                        break
            if full not in sources:
                sources[full] = Source(full)
            c.source = sources[full]
            if c.source.channels:
                tr.channels = max(tr.channels, c.source.channels)
            tr.clips.append(c)
        tr.clips.sort(key=lambda c: c.position)
        s.tracks.append(tr)
    _preflight(s)
    return s


# ------------------------------------------------------------------ Pre-Flight
def _preflight(s, name_limit=31):
    F = s.findings
    offline = [(t, c) for t in s.tracks for c in t.clips if not c.source.exists]
    if offline:
        F.append(Finding("problem", "%d item%s with offline media" % (len(offline), "s" * (len(offline) > 1)),
                         ", ".join("%s %s" % (t.name, s.tc(c.position)) for t, c in offline[:3])))
    multi = [(t, c) for t in s.tracks for c in t.clips if c.takes > 1]
    if multi:
        F.append(Finding("warning", "%d item%s with more than one take" % (len(multi), "s" * (len(multi) > 1)),
                         "Only the active take flies"))
    muted = [(t, c) for t in s.tracks for c in t.clips if c.muted]
    if muted:
        F.append(Finding("warning", "%d muted item%s" % (len(muted), "s" * (len(muted) > 1)),
                         ", ".join("%s %s" % (t.name, s.tc(c.position)) for t, c in muted[:3]) + " - stays home"))
    for t in s.tracks:
        if len(t.name) > name_limit:
            F.append(Finding("warning", "Track name too long", "\"%s\" will be shortened" % t.name))
    for t in s.tracks:
        prev = None
        for c in t.clips:
            if c.muted:
                continue
            if prev is not None and c.position < prev.end - 1e-9:
                ov = prev.end - c.position
                if abs(prev.fade_out - ov) > 0.002 or abs(c.fade_in - ov) > 0.002:
                    F.append(Finding("note", "Crossfade made symmetric", "%s %s: %.3f s" % (t.name, s.tc(c.position), ov)))
            prev = c
    tiny = [(t, c) for t in s.tracks for c in t.clips if int(round(c.length * s.sample_rate)) < 1]
    if tiny:
        F.append(Finding("warning", "%d empty item%s (shorter than a sample)" % (len(tiny), "s" * (len(tiny) > 1)),
                         ", ".join("%s %s" % (t.name, s.tc(c.position)) for t, c in tiny[:3]) + " - stays home"))
    stacked = [t.name for t in s.tracks if len(lanes(t, s.sample_rate)) > 1]
    if stacked:
        F.append(Finding("note", "Stacked items go on extra tracks", ", ".join(stacked[:4])))
    fx_tracks = [t for t in s.tracks if t.fx]
    if fx_tracks or s.master_fx:
        n = sum(len(t.fx) for t in fx_tracks) + len(s.master_fx)
        F.append(Finding("note", "%d plugins on tracks, folders and master" % n,
                         "They don't travel in an AAF - listed with settings in the flight report"))
    rnd = [(t, c) for t in s.tracks for c in t.clips if c.needs_render and not c.muted]
    if rnd:
        reasons = sorted({r for _, c in rnd for r in c.needs_render})
        F.append(Finding("note", "%d item%s will be rendered" % (len(rnd), "s" * (len(rnd) > 1)), ", ".join(reasons)))
    if s.nonaudio:
        kinds = {}
        for n in s.nonaudio:
            kinds[n.kind] = kinds.get(n.kind, 0) + 1
        F.append(Finding("note", "%d non-audio item%s sorted out" % (len(s.nonaudio), "s" * (len(s.nonaudio) > 1)),
                         ", ".join("%d %s" % (v, k) for k, v in sorted(kinds.items()))))
    srs = {c.source.sample_rate for t in s.tracks for c in t.clips if c.source.sample_rate}
    other = sorted(r for r in srs if r != s.sample_rate)
    if other:
        F.append(Finding("problem", "Media at another sample rate", ", ".join("%d Hz" % r for r in other)))
    else:
        F.append(Finding("ok", "Sample rate, frame rate and start TC", "%d Hz - %g fps - starts %s" %
                         (s.sample_rate, s.fps, s.tc(0))))

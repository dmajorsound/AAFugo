"""AAFUGO prototype: write a Session as an AAF with embedded audio (pyaaf2).

Layout (what Avid / Pro Tools / Nuendo write themselves):
  CompositionMob (the session, top level)
    slot 1: Timecode (start = project start offset)
    one sound slot per track and channel: Sequence of Filler / SourceClip / OperationGroup(gain)
      / Transition(Mono Audio Dissolve) - fades are transitions next to filler, crossfades are
      transitions between two clips.
  MasterMob per source file and channel -> SourceMob (PCM, embedded) -> tape SourceMob with the
  file's BWF timecode.
Audio slots use the sample rate as edit rate, so every position is sample-accurate.
Stereo and multichannel files are split into mono essences (as Avid and Pro Tools do), and the
track becomes one mono slot per channel (NAME.L / NAME.R).
"""
import os
import struct
import tempfile

PRESETS = {
    # name length limit, clip gain as, track name suffixes for stereo
    "pt": {"name_limit": 31, "gain": "clip", "label": "Pro Tools"},
    "nuendo": {"name_limit": 0, "gain": "clip", "label": "Nuendo/Cubase"},
    "logic": {"name_limit": 0, "gain": "clip", "label": "Logic"},
    "resolve": {"name_limit": 0, "gain": "clip", "label": "Resolve/Fairlight"},
}

OPDEF_DISSOLVE = "0c3bea41-fc05-11d2-8a29-0050040ef7d2"
OPDEF_GAIN = "9d2ea894-0968-11d3-8a38-0050040ef7d2"
PARAM_AMPLITUDE = "e4962321-2267-11d3-8a4c-0050040ef7d2"


def _register(f):
    gain_param = f.create.ParameterDef(PARAM_AMPLITUDE, "Amplitude", "", "Rational")
    f.dictionary.register_def(gain_param)
    d = f.create.OperationDef(OPDEF_DISSOLVE, "Mono Audio Dissolve", "")
    f.dictionary.register_def(d)
    d.media_kind = "sound"
    d["IsTimeWarp"].value = False
    d["NumberInputs"].value = 2
    d["OperationCategory"].value = "OperationCategory_Effect"
    g = f.create.OperationDef(OPDEF_GAIN, "Mono Audio Gain", "")
    f.dictionary.register_def(g)
    g.media_kind = "sound"
    g["IsTimeWarp"].value = False
    g["NumberInputs"].value = 1
    g["OperationCategory"].value = "OperationCategory_Effect"
    g.parameters.append(gain_param)


def _split_channels(src, tmpdir):
    """Write one mono WAV per channel (PCM, same bit depth). Returns a list of paths."""
    if src.channels == 1:
        return [src.path]
    nb = src.bits // 8
    frame = nb * src.channels
    with open(src.path, "rb") as fi:
        fi.seek(12)
        data = None
        while True:
            ch = fi.read(8)
            if len(ch) < 8:
                break
            cid, size = ch[:4], struct.unpack("<I", ch[4:])[0]
            if cid == b"data":
                data = fi.read(size)
                break
            fi.seek(size + (size & 1), 1)
    outs = []
    base = os.path.splitext(os.path.basename(src.path))[0]
    names = ["L", "R"] if src.channels == 2 else [str(i + 1) for i in range(src.channels)]
    for c in range(src.channels):
        buf = bytearray()
        for off in range(c * nb, len(data) - frame + 1 + c * nb, frame):
            buf += data[off:off + nb]
        p = os.path.join(tmpdir, "%s.%s.wav" % (base, names[c]))
        fmt = struct.pack("<HHIIHH", 1, 1, src.sample_rate, src.sample_rate * nb, nb, src.bits)
        body = b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(buf)) + bytes(buf)
        with open(p, "wb") as fo:
            fo.write(b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body)
        outs.append(p)
    return outs


def _tc_frames(seconds, fps):
    return int(round(seconds * fps))


def write(session, out_path, aaf2, preset="pt", tmpdir=None):
    """Write `session` to `out_path`. `aaf2` is the pyaaf2 module. Returns a summary dict."""
    P = PRESETS[preset]
    sr = session.sample_rate
    fps = int(round(session.fps))
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="aafugo_")
    summary = {"clips": 0, "fades": 0, "crossfades": 0, "gains": 0, "tracks": 0, "slots": []}
    with aaf2.open(out_path, "w") as f:
        _register(f)
        # ---- media: one master mob per source and channel
        masters = {}  # (source path, channel) -> master mob

        def master_for(src, ch):
            key = (src.path, ch)
            if key in masters:
                return masters[key]
            monos = _split_channels(src, tmpdir)
            base = os.path.basename(src.path)
            # the tape: carries the file's BWF timecode
            tape = f.create.SourceMob(os.path.splitext(base)[0])
            tape.descriptor = f.create.TapeDescriptor()
            f.content.mobs.append(tape)
            tslot = tape.create_empty_slot(edit_rate=sr, media_kind="sound", slot_id=1)
            tslot.segment.length = src.time_ref + src.frames + sr * 3600
            tcs = tape.create_timeline_slot(edit_rate=fps)
            tcs.segment = f.create.Timecode(fps, False)
            tcs.segment.start = 0
            for i, mp in enumerate(monos):
                name = base if len(monos) == 1 else "%s.%s" % (os.path.splitext(base)[0], ["L", "R"][i] if len(monos) == 2 else str(i + 1))
                mm = f.create.MasterMob(name)
                f.content.mobs.append(mm)
                tape_clip = tape.create_source_clip(slot_id=1, start=src.time_ref, length=src.frames)
                mm.import_audio_essence(mp, edit_rate=sr, tape=tape_clip)
                masters[(src.path, i)] = mm
            return masters[key]

        comp = f.create.CompositionMob(session.name)
        comp.usage = "Usage_TopLevel"
        f.content.mobs.append(comp)
        # plugins don't travel in an AAF: leave them as comments on the session (and in the flight report)
        try:
            comp.comments["AAFUGO"] = "Exported from REAPER with AAFUGO. Start %s, %d Hz, %g fps." % (
                session.tc(0), sr, session.fps)
            for tr in session.tracks:
                if tr.fx:
                    key = ("Folder " if tr.is_folder else "Track ") + tr.name
                    comp.comments[key[:64]] = "; ".join(x["name"] + (" (bypassed)" if x["bypassed"] else "")
                                                      for x in tr.fx)
            if session.master_fx:
                comp.comments["Master"] = "; ".join(x["name"] for x in session.master_fx)
        except Exception as e:  # comments are a nice-to-have
            summary["comments_error"] = str(e)
        tcslot = comp.create_timeline_slot(edit_rate=fps)
        tcslot.segment = f.create.Timecode(fps, False)
        tcslot.segment.start = _tc_frames(session.offset, fps)
        tcslot.name = "TC1"

        phys = 0
        from .session import lanes as _lanes
        for tr in session.tracks:
          tl = _lanes(tr, sr)
          if tl:
              summary["tracks"] += 1
          for li, clips in enumerate(tl):
            nch = max(c.source.channels for c in clips)
            for ch in range(nch):
                phys += 1
                suffix = "" if nch == 1 else ".%s" % (["L", "R"][ch] if nch == 2 else str(ch + 1))
                base = tr.name if li == 0 else "%s %d" % (tr.name, li + 1)
                if P["name_limit"] and len(base) + len(suffix) > P["name_limit"]:
                    base = base[:P["name_limit"] - len(suffix)].rstrip()
                name = base + suffix
                slot = comp.create_timeline_slot(edit_rate=sr)
                slot.name = name
                slot["PhysicalTrackNumber"].value = phys
                seq = f.create.Sequence(media_kind="sound")
                slot.segment = seq
                cur = 0
                prev = None
                for c in clips:
                    p = int(round(c.position * sr))
                    L = int(round(c.length * sr))
                    ov = (cur - p) if prev is not None else 0
                    if ov > 0:
                        ov = min(ov, L, prev_len)
                        t = f.create.Transition("sound")
                        t.length = ov
                        t["CutPoint"].value = ov // 2
                        og = f.create.OperationGroup("Mono Audio Dissolve", ov, "sound")
                        t["OperationGroup"].value = og
                        seq.components.append(t)
                        summary["crossfades"] += 1
                    else:
                        fo = min(int(round(prev.fade_out * sr)), prev_len) if prev is not None else 0
                        fi = min(int(round(c.fade_in * sr)), L)
                        gap = p - cur
                        if fo:
                            t = f.create.Transition("sound")
                            t.length = fo
                            t["CutPoint"].value = fo
                            t["OperationGroup"].value = f.create.OperationGroup("Mono Audio Dissolve", fo, "sound")
                            seq.components.append(t)
                            summary["fades"] += 1
                        if gap + fo + fi > 0:
                            fl = f.create.Filler("sound", gap + fo + fi)
                            seq.components.append(fl)
                        if fi:
                            t = f.create.Transition("sound")
                            t.length = fi
                            t["CutPoint"].value = 0
                            t["OperationGroup"].value = f.create.OperationGroup("Mono Audio Dissolve", fi, "sound")
                            seq.components.append(t)
                            summary["fades"] += 1
                    srcch = min(ch, c.source.channels - 1)
                    mm = master_for(c.source, srcch)
                    start = int(round(c.offset * sr))
                    sc = mm.create_source_clip(slot_id=1, start=start, length=L)
                    seg = sc
                    if abs(c.gain - 1.0) > 1e-6:
                        og = f.create.OperationGroup("Mono Audio Gain", L, "sound")
                        og.segments.append(sc)
                        cv = f.create.ConstantValue("Amplitude", c.gain)
                        og.parameters.append(cv)
                        seg = og
                        summary["gains"] += 1
                    seq.components.append(seg)
                    summary["clips"] += 1
                    summary["slots"].append((name, p, L, start))
                    cur = p + L
                    prev = c
                    prev_len = L
                if prev is not None and prev.fade_out > 0:
                    fo = min(int(round(prev.fade_out * sr)), prev_len)
                    t = f.create.Transition("sound")
                    t.length = fo
                    t["CutPoint"].value = fo
                    t["OperationGroup"].value = f.create.OperationGroup("Mono Audio Dissolve", fo, "sound")
                    seq.components.append(t)
                    seq.components.append(f.create.Filler("sound", fo))
                    summary["fades"] += 1
    return summary

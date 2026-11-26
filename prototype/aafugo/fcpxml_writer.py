"""AAFUGO prototype: write a Session as FCPXML (Final Cut Pro X interchange) for Logic Pro.

Times are rational seconds at the sample rate ("N/48000s"), so positions stay sample-accurate.
The session is one gap on the primary storyline from the start timecode; every REAPER track is
a lane of connected audio clips (lane 1 = first track). Clip gain -> adjust-volume amount (dB),
fades -> fadeIn / fadeOut on the volume. Media is linked, not copied.
"""
import math
import os
from urllib.parse import quote
from xml.sax.saxutils import quoteattr


def _t(samples, sr):
    return "0s" if samples == 0 else "%d/%ds" % (samples, sr)


def _db(g):
    return "%.2fdB" % (20 * math.log10(g)) if g > 0 else "-96dB"


def write(session, out_path):
    sr = session.sample_rate
    fps = int(round(session.fps))
    S = lambda sec: int(round(sec * sr))
    t0 = S(session.offset)
    assets, X, summary = {}, [], {"clips": 0, "fades": 0, "gains": 0, "tracks": 0}
    res = ['    <format id="r1" name="FFVideoFormat1080p%d" frameDuration="100/%ds" width="1920" height="1080"/>' % (fps, fps * 100)]
    end = 0
    lanes = []
    for tr in session.tracks:
        clips = [c for c in tr.clips if not c.muted and c.source and c.source.exists and c.source.frames]
        if clips:
            lanes.append((tr, clips))
            end = max(end, max(S(c.end) for c in clips))
    for tr, clips in lanes:
        for c in clips:
            src = c.source
            if src.path not in assets:
                rid = "r%d" % (len(assets) + 2)
                assets[src.path] = rid
                url = "file://" + quote(os.path.abspath(src.path))
                res.append('    <asset %s>' % " ".join('%s=%s' % (k, quoteattr(str(v))) for k, v in [
                    ("id", rid), ("name", os.path.splitext(os.path.basename(src.path))[0]),
                    ("start", _t(src.time_ref, sr)), ("duration", _t(src.frames, sr)), ("hasAudio", 1),
                    ("audioSources", 1), ("audioChannels", src.channels), ("audioRate", src.sample_rate)]))
                res.append('      <media-rep kind="original-media" src=%s/>' % quoteattr(url))
                res.append('    </asset>')
    for lane, (tr, clips) in enumerate(lanes, start=1):
        summary["tracks"] += 1
        role = "dialogue" if tr.name.upper().startswith(("DIA", "DX", "DIAL")) else (
            "music" if tr.name.upper().startswith(("MUS", "MX")) else "effects")
        for c in clips:
            src = c.source
            body = []
            vol = []
            if c.fade_in > 0:
                vol.append('<fadeIn type="linear" duration="%s"/>' % _t(S(c.fade_in), sr))
            if c.fade_out > 0:
                vol.append('<fadeOut type="linear" duration="%s"/>' % _t(S(c.fade_out), sr))
            if abs(c.gain - 1) > 1e-6 or vol:
                amt = ' amount="%s"' % _db(c.gain) if abs(c.gain - 1) > 1e-6 else ""
                if vol:
                    body.append('<adjust-volume%s><param name="amount">%s</param></adjust-volume>' % (amt, "".join(vol)))
                else:
                    body.append('<adjust-volume%s/>' % amt)
                summary["gains"] += abs(c.gain - 1) > 1e-6
                summary["fades"] += len(vol)
            attrs = [("ref", assets[src.path]), ("lane", lane), ("offset", _t(t0 + S(c.position), sr)),
                     ("name", c.name), ("duration", _t(S(c.length), sr)),
                     ("start", _t(src.time_ref + S(c.offset), sr)), ("audioRole", role)]
            a = " ".join('%s=%s' % (k, quoteattr(str(v))) for k, v in attrs)
            X.append('              <asset-clip %s>%s</asset-clip>' % (a, "".join(body)) if body else
                     '              <asset-clip %s/>' % a)
            summary["clips"] += 1
    doc = ['<?xml version="1.0" encoding="UTF-8"?>', '<!DOCTYPE fcpxml>', '<fcpxml version="1.10">', '  <resources>']
    doc += res + ['  </resources>', '  <library>', '    <event name="AAFUGO">',
                  '      <project name=%s>' % quoteattr(session.name),
                  '        <sequence format="r1" duration="%s" tcStart="%s" tcFormat="NDF" audioLayout="stereo" audioRate="%dk">'
                  % (_t(end, sr), _t(t0, sr), sr // 1000),
                  '          <spine>',
                  '            <gap name="Gap" offset="%s" start="%s" duration="%s">' % (_t(t0, sr), _t(t0, sr), _t(end, sr))]
    doc += X + ['            </gap>', '          </spine>', '        </sequence>', '      </project>', '    </event>',
                '  </library>', '</fcpxml>']
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(doc) + "\n")
    return summary

"""AAFUGO prototype: write a Session as DAWproject 1.0 (zip with project.xml, metadata.xml, audio).

Timeline in seconds. Positions are written as absolute time of day (project start offset +
position), so 01:00:00:00 in REAPER lands at 01:00:00:00 in Cubase/Nuendo when their project
starts at 00:00:00:00.
DAWproject clips have no gain: clip gain becomes the track's volume automation (hold points at
each clip), like AAFUGO's Logic mode. Fades and crossfades are clip fades in seconds.
Audio is embedded in the zip (audio/...), stereo files stay stereo.
"""
import os
import re
import zipfile

from . import plugin_state
from xml.sax.saxutils import quoteattr

COLORS = ["#4C93DC", "#E08A3C", "#5BAF6A", "#B06FC9", "#D9534F", "#3FB2B5", "#C9A43B", "#8A8F98"]


def _a(**kw):
    return " ".join("%s=%s" % (k.rstrip("_"), quoteattr(str(v))) for k, v in kw.items() if v is not None)


def write(session, out_path, absolute_time=True):
    ids = iter(range(1, 10 ** 9))
    nid = lambda: "id%d" % next(ids)
    t0 = session.offset if absolute_time else 0.0
    X = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Project version="1.0">',
         '  <Application name="AAFUGO" version="0.1"/>',
         '  <Transport>',
         '    <Tempo %s/>' % _a(max="666", min="20", unit="bpm", value="120", id=nid(), name="Tempo"),
         '    <TimeSignature denominator="4" numerator="4" id="%s"/>' % nid(),
         '  </Transport>', '  <Structure>']
    master = nid()
    tracks = []
    files = {}  # source path -> path in zip
    states = {}  # path in zip -> bytes
    summary = {"clips": 0, "fades": 0, "gains": 0, "tracks": 0, "folders": 0, "plugins": 0, "plugins_skipped": 0}

    def devices(fxlist, pad):
        out = []
        for fx in fxlist:
            if fx["type"] == "VST":
                r = plugin_state.vst2_fxp(fx)
                if r:
                    data, uid = r
                    plain, vendor = plugin_state.vst2_ids(fx)
                    path = "plugins/%s_%d.fxp" % (re.sub(r"[^A-Za-z0-9]+", "_", plain).strip("_"), len(states) + 1)
                    states[path] = data
                    out += [pad + '<Vst2Plugin %s>' % _a(deviceID=uid, deviceName=plain, deviceRole="audioFX",
                                                        deviceVendor=vendor, loaded="true", id=nid(), name=plain),
                            pad + '  <Enabled value="%s" id="%s" name="On/Off"/>' % ("false" if fx["bypassed"] else "true", nid()),
                            pad + '  <State path=%s/>' % quoteattr(path),
                            pad + '</Vst2Plugin>']
                    summary["plugins"] += 1
                    continue
            summary["plugins_skipped"] += 1
        return ([pad[:-2] + "<Devices>"] + out + [pad[:-2] + "</Devices>"]) if out else []

    def channel(pad, cid, nch, dest, role, fxlist, vol_id=None):
        return ([pad + '<Channel %s>' % _a(audioChannels=nch, destination=dest, role=role, solo="false", id=cid)]
                + devices(fxlist, pad + "    ")
                + [pad + '  <Mute value="false" id="%s" name="Mute"/>' % nid(),
                   pad + '  <Pan max="1" min="0" unit="normalized" value="0.5" id="%s" name="Pan"/>' % nid(),
                   pad + '  <Volume max="2" min="0" unit="linear" value="1" id="%s" name="Volume"/>' % (vol_id or nid()),
                   pad + '</Channel>'])

    # the track tree: folders become group tracks (contentType "tracks") whose channel is a submix
    stack = [master]  # destination channel for the current depth
    open_depth = 0
    for i, tr in enumerate(session.tracks):
        while open_depth > tr.depth:
            X.append("    " + "  " * open_depth + "</Track>")
            open_depth -= 1
            stack.pop()
        pad = "    " + "  " * (tr.depth + 1)
        clips = [c for c in tr.clips if not c.muted and c.source and c.source.exists and c.source.frames]
        if tr.is_folder:
            tid, cid = nid(), nid()
            X.append(pad[:-2] + '<Track %s>' % _a(contentType="tracks", loaded="true", id=tid, name=tr.name,
                                                  color=tr.color or COLORS[i % len(COLORS)]))
            X += channel(pad, cid, 2, stack[-1], "submix", tr.fx)
            stack.append(cid)
            open_depth += 1
            summary["folders"] += 1
            continue
        if not clips and not tr.fx:
            continue
        tid, cid, vol = nid(), nid(), nid()
        nch = max([c.source.channels for c in clips] or [2])
        if clips:
            tracks.append((tr, clips, tid, vol))
        X.append(pad[:-2] + '<Track %s>' % _a(contentType="audio", loaded="true", id=tid, name=tr.name,
                                              color=tr.color or COLORS[i % len(COLORS)]))
        X += channel(pad, cid, nch, stack[-1], "regular", tr.fx, vol)
        X.append(pad[:-2] + '</Track>')
        summary["tracks"] += 1
    while open_depth > 0:
        X.append("    " + "  " * open_depth + "</Track>")
        open_depth -= 1
    X.append('    <Track %s>' % _a(contentType="audio", loaded="true", id=nid(), name="Master"))
    X += channel("      ", master, 2, None, "master", session.master_fx)
    X += ['    </Track>', '  </Structure>',
          '  <Arrangement id="%s">' % nid(), '    <Lanes timeUnit="seconds" id="%s">' % nid()]
    for tr, clips, tid, vol in tracks:
        X.append('      <Lanes track="%s" id="%s">' % (tid, nid()))
        X.append('        <Clips id="%s">' % nid())
        for c in clips:
            src = c.source
            if src.path not in files:
                base = os.path.basename(src.path)
                name, n = base, 1
                while name in files.values():
                    n += 1
                    name = "%s_%d%s" % (os.path.splitext(base)[0], n, os.path.splitext(base)[1])
                files[src.path] = name
            X.append('          <Clip %s>' % _a(time="%.9f" % (t0 + c.position), duration="%.9f" % c.length,
                                                 contentTimeUnit="seconds", playStart="%.9f" % c.offset,
                                                 fadeTimeUnit="seconds", fadeInTime="%.9f" % c.fade_in,
                                                 fadeOutTime="%.9f" % c.fade_out, name=c.name))
            X.append('            <Audio %s>' % _a(channels=src.channels, sampleRate=src.sample_rate,
                                                     duration="%.9f" % src.duration, id=nid()))
            X.append('              <File path=%s/>' % quoteattr("audio/" + files[src.path]))
            X.append('            </Audio>')
            X.append('          </Clip>')
            summary["clips"] += 1
            summary["fades"] += (c.fade_in > 0) + (c.fade_out > 0)
        X.append('        </Clips>')
        if any(abs(c.gain - 1) > 1e-6 for c in clips):
            X.append('        <Points id="%s" unit="linear">' % nid())
            X.append('          <Target parameter="%s"/>' % vol)
            for k, c in enumerate(clips):
                X.append('          <RealPoint time="%.9f" value="%.6f" interpolation="hold"/>' % (t0 + c.position, c.gain))
                nxt = clips[k + 1] if k + 1 < len(clips) else None
                if nxt is None or nxt.position > c.end + 1e-9:
                    X.append('          <RealPoint time="%.9f" value="1" interpolation="hold"/>' % (t0 + c.end))
                if abs(c.gain - 1) > 1e-6:
                    summary["gains"] += 1
            X.append('        </Points>')
        X.append('      </Lanes>')
    X += ['    </Lanes>', '  </Arrangement>', '  <Scenes/>', '</Project>']
    meta = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<MetaData>\n  <Title>%s</Title>\n'
            '  <Comment>Exported from REAPER with AAFUGO. Start %s, %d Hz, %g fps.</Comment>\n</MetaData>\n'
            % (session.name, session.tc(0), session.sample_rate, session.fps))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.xml", "\n".join(X) + "\n")
        z.writestr("metadata.xml", meta)
        for name, data in states.items():
            z.writestr(name, data)
        for p, name in files.items():
            z.write(p, "audio/" + name, compress_type=zipfile.ZIP_STORED)
    return summary

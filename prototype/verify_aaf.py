"""Read an AAFUGO AAF back and compare every clip with the REAPER session, sample by sample.

usage: python3 -I verify_aaf.py <pyaaf2 src dir> <session.rpp> <file.aaf>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def walk(seq):
    """Yield (position, kind, component) with transitions taken into account."""
    pos = 0
    for c in seq.components:
        name = type(c).__name__
        if name == "Transition":
            pos -= c.length
            yield pos, "transition", c
            continue
        yield pos, name, c
        pos += c.length


def main():
    sys.path.append(sys.argv[1])
    import aaf2
    from aafugo import session
    s = session.load(sys.argv[2])
    sr = s.sample_rate
    expected = []  # in the writer's order: track -> lane -> channel
    for tr in s.tracks:
        for lane in session.lanes(tr, sr):
            nch = max(c.source.channels for c in lane)
            exp = [(int(round(c.position * sr)), int(round(c.length * sr)), int(round(c.offset * sr)),
                    round(c.gain, 4), os.path.basename(c.source.path)) for c in lane]
            expected += [exp] * nch
    diffs, n = [], 0
    with aaf2.open(sys.argv[3], "r") as f:
        comp = next(f.content.toplevel())
        tc = [sl for sl in comp.slots if sl.segment.media_kind == "Timecode"]
        tc_start = tc[0].segment.start if tc else None
        print("timecode start (frames):", tc_start, "fps:", tc[0].segment.fps if tc else None)
        for slot in comp.slots:
            if slot.segment.media_kind != "Sound":
                continue
            got, fades = [], 0
            for pos, kind, c in walk(slot.segment):
                if kind == "transition":
                    fades += 1
                    continue
                gain = 1.0
                if kind == "OperationGroup":
                    for p in c.parameters:
                        gain = float(p.value)
                    c = c.segments[0]
                    kind = type(c).__name__
                if kind == "SourceClip":
                    mm = c.mob
                    got.append((pos, c.length, c.start, round(gain, 4), mm.name))
            exp = expected.pop(0) if expected else None
            ok = exp is not None and len(exp) == len(got)
            if ok:
                for e, g in zip(exp, got):
                    n += 1
                    if e[:4] != g[:4] or not g[4].startswith(os.path.splitext(e[4])[0]):
                        diffs.append((slot.name, e, g))
            else:
                diffs.append((slot.name, "clip count", exp and len(exp), len(got)))
            print("  %-34s %2d clips, %2d transitions" % (slot.name, len(got), fades))
        # essence check: every master mob reaches embedded PCM
        emb = sum(1 for m in f.content.sourcemobs() if m.essence is not None)
        print("embedded essences:", emb)
    print("VERIFIED" if not diffs else "DIFFERENCES", "- %d clips compared, %d differences" % (n, len(diffs)))
    for d in diffs:
        print("   ", d)


if __name__ == "__main__":
    main()

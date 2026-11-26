"""AAFUGO format prototype.

usage: python3 run_proto.py <session.rpp> <out dir> [targets...] [--pyaaf2 <pyaaf2 src dir>]
targets: pt nuendo logic resolve (AAF, needs pyaaf2), dawproject, sesx, fcpxml
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SFX = {"pt": "_PT", "nuendo": "_Nuendo-Cubase", "logic": "_Logic", "resolve": "_Resolve",
       "dawproject": "_Nuendo-Cubase", "sesx": "_Audition", "fcpxml": "_Logic"}


def main():
    args = sys.argv[1:]
    pyaaf2_dir = None
    if "--pyaaf2" in args:
        i = args.index("--pyaaf2")
        pyaaf2_dir = args[i + 1]
        del args[i:i + 2]
    rpp, out = args[0], args[1]
    targets = args[2:] or ["dawproject"]
    from aafugo import session, nonaudio
    os.makedirs(out, exist_ok=True)
    text = open(rpp, encoding="utf-8", errors="replace").read()
    sorted_text, moved = nonaudio.sort_rpp(text)
    base = os.path.splitext(os.path.basename(rpp))[0]
    sorted_path = os.path.join(out, base + "_sorted.rpp")
    open(sorted_path, "w", encoding="utf-8").write(sorted_text)
    s = session.load(rpp)
    print("PRE-FLIGHT  %s  (%s)" % (s.name, ", ".join(targets)))
    for f in s.findings:
        print("  ", f)
    print("non-audio sorted:", moved, "->", sorted_path)
    for t in targets:
        if t in ("pt", "nuendo", "logic", "resolve"):
            if not pyaaf2_dir:
                print("skip", t, "(AAF needs --pyaaf2)")
                continue
            sys.path.append(pyaaf2_dir)
            import aaf2
            from aafugo import aaf_writer
            p = os.path.join(out, base + SFX[t] + ".aaf")
            r = aaf_writer.write(s, p, aaf2, preset=t)
        elif t == "dawproject":
            from aafugo import dawproject_writer
            p = os.path.join(out, base + SFX[t] + ".dawproject")
            r = dawproject_writer.write(s, p)
        elif t == "sesx":
            from aafugo import sesx_writer
            p = os.path.join(out, base + SFX[t] + ".sesx")
            r = sesx_writer.write(s, p)
        elif t == "fcpxml":
            from aafugo import fcpxml_writer
            p = os.path.join(out, base + SFX[t] + ".fcpxml")
            r = fcpxml_writer.write(s, p)
        else:
            print("unknown target", t)
            continue
        print("wrote", p, {k: v for k, v in r.items() if k != "slots"})
        try:
            from aafugo import report_writer
            rp = os.path.splitext(p)[0] + "_FlightReport.pdf"
            report_writer.write(s, rp, target=t, export_file=os.path.basename(p),
                                logo=os.path.join(HERE, "..", "dmajor_mark.png"))
            print("wrote", rp)
            rpd = os.path.splitext(p)[0] + "_FlightReport_Dark.pdf"
            report_writer.write(s, rpd, target=t, export_file=os.path.basename(p),
                                logo=os.path.join(HERE, "..", "dmajor_mark_dark.png"), dark=True)
            print("wrote", rpd)
        except ImportError as e:
            print("no flight report:", e)


if __name__ == "__main__":
    main()

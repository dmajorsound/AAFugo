"""Sort non-audio items (MIDI, video, notes, subprojects, generators) onto their own tracks.

In the extension this happens in REAPER through the API. The prototype does the same to the .rpp
text, so the result can be opened in REAPER and checked: <name>_sorted.rpp next to the original.
"""
from . import session as S

TRACK_NAME = {"MIDI": "NON-AUDIO – MIDI", "VIDEO": "NON-AUDIO – VIDEO", "NOTES": "NON-AUDIO – NOTES",
              "SUBPROJECT": "NON-AUDIO – SUBPROJECTS", "GENERATOR": "NON-AUDIO – GENERATORS",
              "OTHER": "NON-AUDIO – OTHER"}
ORDER = ["VIDEO", "MIDI", "NOTES", "SUBPROJECT", "GENERATOR", "OTHER"]


def _kind(block_lines):
    node = S.parse_rpp("\n".join(block_lines))
    takes, sel = S._takes(node)
    src = next((c for c in takes[sel]["children"] if c.tag == "SOURCE"), None)
    kind = src.args[0] if src and src.args else ""
    if kind == "SECTION" and src.child("SOURCE"):
        kind = src.child("SOURCE").args[0]
    if kind in S.AUDIO_SOURCES:
        return None
    return S.NONAUDIO_KIND.get(kind, "OTHER")


def sort_rpp(text):
    """Return (new_text, moved) where moved maps kind -> number of items."""
    lines = text.splitlines()
    out, depth, i = [], 0, 0
    buckets = {}
    in_track = False
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("<"):
            tag = s[1:].split()[0] if len(s) > 1 else ""
            if depth == 1 and tag == "TRACK":
                in_track = True
            if depth == 2 and in_track and tag == "ITEM":
                # collect the whole ITEM block
                block, d = [], 0
                while i < len(lines):
                    b = lines[i]
                    bs = b.strip()
                    block.append(b)
                    if bs.startswith("<"):
                        d += 1
                    elif bs == ">":
                        d -= 1
                        if d == 0:
                            break
                    i += 1
                i += 1
                k = _kind(block)
                if k:
                    buckets.setdefault(k, []).append(block)
                else:
                    out.extend(block)
                continue
            depth += 1
        elif s == ">":
            depth -= 1
            if depth == 1:
                in_track = False
            if depth == 0:
                # end of project: add the non-audio tracks before the closing bracket
                for k in ORDER:
                    if k in buckets:
                        out.append("  <TRACK")
                        out.append("    NAME \"%s\"" % TRACK_NAME[k])
                        for b in buckets[k]:
                            out.extend(b)
                        out.append("  >")
        out.append(ln)
        i += 1
    return "\n".join(out) + "\n", {k: len(v) for k, v in buckets.items()}

"""Make a small synthetic REAPER session for testing AAFUGO's export.

Writes <out>/TestSession.rpp and <out>/Audio/*.wav (Broadcast WAV, 48 kHz, 24 bit, with a bext
time reference). The session has: dialog on two tracks, a crossfade, fades, item gain, a stereo
atmo, an item with take FX, an item with playrate, a muted item, an item with two takes, and
non-audio items (MIDI, video, empty item with notes).
"""
import math
import os
import struct
import sys

SR = 48000


def bwf(path, seconds, freq, channels=1, time_ref=0, desc=""):
    n = int(seconds * SR)
    frames = bytearray()
    for i in range(n):
        env = min(1.0, i / 480.0, (n - i) / 480.0)
        for c in range(channels):
            v = 0.3 * env * math.sin(2 * math.pi * freq * (1 + 0.5 * c) * i / SR)
            s = int(v * 8388607)
            frames += struct.pack("<i", s)[:3]
    fmt = struct.pack("<HHIIHH", 1, channels, SR, SR * 3 * channels, 3 * channels, 24)
    bext = bytearray(602)
    d = desc.encode()[:256]
    bext[0:len(d)] = d
    bext[256:256 + 7] = b"AAFUGO "
    bext[320:330] = b"2026-11-26"
    bext[330:338] = b"01:00:00"
    struct.pack_into("<Q", bext, 338, time_ref)
    struct.pack_into("<H", bext, 346, 1)
    chunks = b"bext" + struct.pack("<I", len(bext)) + bytes(bext)
    chunks += b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(frames)) + bytes(frames)
    if len(frames) % 2:
        chunks += b"\0"
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks)


def item(pos, length, src, soffs=0.0, name=None, fin=0.0, fout=0.0, vol=1.0, mute=0, playrate=1.0,
         takefx=False, extra_take=None):
    name = name or os.path.basename(src)
    s = ["    <ITEM",
         f"      POSITION {pos:.10f}",
         "      SNAPOFFS 0",
         f"      LENGTH {length:.10f}",
         "      LOOP 0",
         "      ALLTAKES 0",
         f"      FADEIN 1 {fin:.10f} 0 1 0 0 0",
         f"      FADEOUT 1 {fout:.10f} 0 1 0 0 0",
         f"      MUTE {mute} 0",
         "      SEL 0",
         f"      NAME \"{name}\"",
         f"      VOLPAN {vol:.6f} 0 1 -1",
         f"      SOFFS {soffs:.10f}",
         f"      PLAYRATE {playrate:.6f} 1 0 -1 0 0.0025",
         "      CHANMODE 0"]
    if takefx:
        s += ["      <TAKEFX", "        SHOW 0", "        <JS loser/3BandEQ \"\"", "        >", "      >"]
    s += ["      <SOURCE WAVE", f"        FILE \"{src}\"", "      >"]
    if extra_take:
        s += ["      TAKE SEL", f"      NAME \"{os.path.basename(extra_take)}\"", "      VOLPAN 1 0 1 -1",
              "      SOFFS 0", "      PLAYRATE 1 1 0 -1 0 0.0025", "      CHANMODE 0",
              "      <SOURCE WAVE", f"        FILE \"{extra_take}\"", "      >"]
    s.append("    >")
    return "\n".join(s)


def track(name, items, nchan=2):
    return "\n".join([f"  <TRACK", f"    NAME \"{name}\"", f"    NCHAN {nchan}"] + items + ["  >"])


def main(out):
    a = os.path.join(out, "Audio")
    os.makedirs(a, exist_ok=True)
    files = {
        "DX_01.wav": (8, 220, 1), "DX_02.wav": (8, 260, 1), "DX_03.wav": (6, 300, 1),
        "DX_04_alt.wav": (6, 330, 1), "ATMO_forest.wav": (14, 110, 2), "FX_door.wav": (3, 900, 1),
        "FX_steps.wav": (5, 700, 1), "MX_cue1.wav": (12, 440, 2),
    }
    tc = 3600 * SR  # sources stamped at 01:00:00:00
    for fn, (sec, fr, ch) in files.items():
        bwf(os.path.join(a, fn), sec, fr, ch, tc, fn)
    # project time: PROJOFFS 3600 -> position 0 shows as 01:00:00:00
    tracks = [
        track("DIA 1", [
            item(1.0, 4.0, "Audio/DX_01.wav", soffs=1.0, fin=0.05, fout=0.5, vol=0.707946),
            # crossfade with the next item: 0.5 s overlap
            item(4.5, 4.0, "Audio/DX_02.wav", soffs=2.0, fin=0.5, fout=0.1),
            item(10.0, 3.0, "Audio/DX_03.wav", soffs=0.5, takefx=True),  # take FX -> render
        ]),
        track("DIA 2", [
            item(2.0, 3.0, "Audio/DX_03.wav", soffs=1.0, vol=1.412538, extra_take="Audio/DX_04_alt.wav"),
            item(6.0, 2.0, "Audio/DX_04_alt.wav", soffs=0.0, playrate=1.05),  # playrate -> render
            item(9.0, 1.0, "Audio/DX_04_alt.wav", soffs=2.0, mute=1),
        ]),
        track("ATMO forest night rain long version", [
            item(0.0, 13.0, "Audio/ATMO_forest.wav", soffs=0.5, fin=2.0, fout=3.0, vol=0.5)]),
        track("FX", [
            item(3.0, 1.5, "Audio/FX_door.wav", soffs=0.5, fin=0.01, fout=0.2),
            item(5.0, 4.0, "Audio/FX_steps.wav", soffs=0.5, fin=0.01, fout=0.2),
            # a MIDI item and an empty item with notes on an audio track
            "\n".join(["    <ITEM", "      POSITION 8.0", "      LENGTH 2.0", "      NAME \"hit\"",
                       "      <SOURCE MIDI", "        HASDATA 1 960 QN", "        E 0 90 3c 60", "        E 480 80 3c 00",
                       "      >", "    >"]),
            "\n".join(["    <ITEM", "      POSITION 11.0", "      LENGTH 1.0", "      <NOTES",
                       "        |add door slam here", "      >", "    >"]),
        ]),
        track("MUSIC", [item(1.0, 11.0, "Audio/MX_cue1.wav", soffs=0.0, fin=0.5, fout=2.0)]),
        track("VIDEO", [
            "\n".join(["    <ITEM", "      POSITION 0.0", "      LENGTH 14.0", "      NAME \"Picture_v12.mov\"",
                       "      <SOURCE VIDEO", "        FILE \"Video/Picture_v12.mov\"", "      >", "    >"])]),
    ]
    rpp = "\n".join([
        "<REAPER_PROJECT 0.1 \"7.27/macOS-arm64\" 1764115200",
        "  SAMPLERATE 48000 0 0",
        "  PROJOFFS 3600 0 0",
        "  SMPTESYNC 0 25 100 40 1000 300 0 0 1 0 0",
        "  TIMEMODE 5 0 -1 25 0 0 -1",
    ] + tracks + [">"]) + "\n"
    with open(os.path.join(out, "TestSession.rpp"), "w") as f:
        f.write(rpp)
    os.makedirs(os.path.join(out, "Video"), exist_ok=True)
    open(os.path.join(out, "Video", "Picture_v12.mov"), "wb").write(b"\0" * 1024)  # stand-in, not a real movie
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "TestSession")

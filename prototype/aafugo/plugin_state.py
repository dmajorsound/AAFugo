"""Turn REAPER's stored plugin state into files other hosts can load.

VST2: REAPER stores base64 of [uniqueID, 0xFEED5EEE, pin maps, chunk size, flags, chunk] and the
program name on the last line. The chunk goes into a standard .fxp (opaque chunk, 'FPCh').
VST3 / AU / CLAP states are not converted yet; JS plugins only exist in REAPER.
"""
import base64
import re
import struct


def vst2_fxp(fx):
    lines = fx.get("state") or []
    if len(lines) < 2:
        return None
    try:
        raw = base64.b64decode("".join(lines[:-1]))
        tail = base64.b64decode(lines[-1])
    except Exception:
        return None
    if len(raw) < 12:
        return None
    uid, magic = struct.unpack("<II", raw[:8])
    if magic not in (0xFEED5EEE, 0xFEED5EEF):
        return None
    o = 8
    nin = struct.unpack("<i", raw[o:o + 4])[0]
    o += 4 + 8 * nin
    nout = struct.unpack("<i", raw[o:o + 4])[0]
    o += 4 + 8 * nout
    size = struct.unpack("<I", raw[o:o + 4])[0]
    o += 4 + 8  # chunk size, then 8 bytes of flags
    chunk = raw[o:o + size]
    if len(chunk) != size:
        return None
    m = re.match(rb"\x00?([^\x00]*)", tail)
    prg = (m.group(1) if m else b"")[:27]
    body = (b"FPCh" + struct.pack(">iIiI", 1, uid, 1, 1) + prg.ljust(28, b"\0") +
            struct.pack(">I", len(chunk)) + chunk)
    return b"CcnK" + struct.pack(">I", len(body)) + body, uid


def vst2_ids(fx):
    """deviceID / vendor for a REAPER VST line like  "VST: ReaEQ (Cockos)" reaeq.vst.dylib 0 "" 1919247729<...>"""
    name = fx["name"]
    m = re.match(r"(?:VSTi?3?i?|AUi?|CLAPi?):\s*(.*?)(?:\s*\(([^)]*)\))?$", name)
    plain, vendor = (m.group(1), m.group(2)) if m else (name, None)
    return plain, vendor

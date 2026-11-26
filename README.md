# AAFUGO – Session Export for REAPER

Free REAPER extension by dmajorsound: exports a REAPER session for the mixer, as AAF (Pro Tools,
Nuendo/Cubase, Logic, Resolve/Fairlight) or DAWproject, with a Pre-Flight check, non-audio items
sorted onto their own tracks, a Verified read-back and a Flight Report.

**Status: 0.1 beta** – REAPER extension with *Export session…* (DAWproject) and *Sort non-audio items*. AAF follows.

## What is here
- `src/core` – C++ core: reads the REAPER session (tracks, folders, items, fades, crossfades,
  item gain, takes, colors, plugins), Pre-Flight list, non-audio sorting, DAWproject writer.
- `src/ext` – the REAPER extension (reaper_aafugo.dylib / .dll).
- `src/cli` – `aafugo-cli`, the export without REAPER, for testing.
- `prototype/` – the Python format prototype (AAF via pyaaf2, DAWproject, FCPXML, Flight Report
  PDF) that the C++ code follows. The DAWproject output of both is byte-identical.
- `installer/mac_dmg` – background of the Mac disk image (same layout as OLAAF).

## Build
    cmake -S . -B build && cmake --build build
    build/aafugo-cli Session.rpp out/

License: GNU GPL v2 or later.

// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.
#pragma once

#include <string>

#include "session.h"

namespace aafugo {

struct ExportSummary {
  int clips = 0, fades = 0, gains = 0, tracks = 0, folders = 0, plugins = 0, pluginsSkipped = 0;
  std::string error;  // empty = written
};

// Write DAWproject 1.0: a zip with project.xml, metadata.xml, the audio (embedded) and plugin
// states. Folders become group tracks, VST2 plugins travel as .fxp states, clip gain becomes the
// track's volume automation (DAWproject clips have no gain). Positions are time of day, so
// 01:00:00:00 in REAPER stays 01:00:00:00.
ExportSummary writeDawProject(const Session &s, const std::string &outPath);

// VST2 state as REAPER stores it (base64 lines) -> a standard .fxp (opaque chunk). Empty if it
// isn't a VST2 state.
std::string vst2Fxp(const Plugin &p, unsigned *uniqueId);

}  // namespace aafugo

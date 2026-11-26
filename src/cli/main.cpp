// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.
//
// aafugo-cli: the export without REAPER, for testing.
//   aafugo-cli <session.rpp> <out dir> [dawproject]
// Prints the Pre-Flight list, writes <name>_sorted.rpp (non-audio sorted out) and the export.

#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>

#include "../core/dawproject.h"
#include "../core/session.h"

int main(int argc, char **argv) {
  if (argc < 3) {
    std::fprintf(stderr, "usage: aafugo-cli <session.rpp> <out dir> [dawproject]\n");
    return 2;
  }
  std::string rpp = argv[1], out = argv[2];
  std::string target = argc > 3 ? argv[3] : "dawproject";
  try {
    aafugo::Session s = aafugo::loadRpp(rpp);
    std::printf("PRE-FLIGHT  %s  (%s)\n", s.name.c_str(), target.c_str());
    for (auto &f : s.findings) std::printf("   [%s] %s%s%s\n", f.level.c_str(), f.title.c_str(), f.detail.empty() ? "" : " - ", f.detail.c_str());
    std::ifstream in(rpp, std::ios::binary);
    std::stringstream ss;
    ss << in.rdbuf();
    std::vector<std::pair<std::string, int>> moved;
    std::string sorted = aafugo::sortNonAudio(ss.str(), &moved);
    std::string sp = out + "/" + s.name + "_sorted.rpp";
    std::ofstream(sp, std::ios::binary) << sorted;
    std::printf("non-audio sorted:");
    for (auto &m : moved) std::printf(" %s %d", m.first.c_str(), m.second);
    std::printf(" -> %s\n", sp.c_str());
    if (target == "dawproject") {
      std::string p = out + "/" + s.name + "_Nuendo-Cubase.dawproject";
      auto r = aafugo::writeDawProject(s, p);
      if (!r.error.empty()) {
        std::fprintf(stderr, "error: %s\n", r.error.c_str());
        return 1;
      }
      std::printf("wrote %s  clips %d, fades %d, gains %d, tracks %d, folders %d, plugins %d (skipped %d)\n", p.c_str(), r.clips,
                  r.fades, r.gains, r.tracks, r.folders, r.plugins, r.pluginsSkipped);
    } else {
      std::fprintf(stderr, "unknown target %s\n", target.c_str());
      return 2;
    }
  } catch (std::exception &e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    return 1;
  }
  return 0;
}

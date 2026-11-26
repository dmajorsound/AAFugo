// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.
//
// The session model every writer works from: tracks -> clips (audio only), the non-audio items
// that were sorted out, folders with their plugins, and the Pre-Flight findings.
// Times are seconds of REAPER project time; `offset` is the project start offset (PROJOFFS), so
// the timecode of a position is offset + position.
#pragma once

#include <memory>
#include <string>
#include <vector>

namespace aafugo {

struct Source {
  std::string path;
  bool exists = false;
  bool isWav = false;
  int sampleRate = 0;
  int channels = 0;
  int bits = 0;
  long long frames = 0;
  unsigned long long timeRef = 0;  // BWF time reference, samples since midnight
  double duration() const { return (frames && sampleRate) ? double(frames) / sampleRate : 0.0; }
};

struct Plugin {
  std::string name;   // "VST: ReaEQ (Cockos)", "JS: loser/Saturation"
  std::string type;   // VST, VST3, AU, JS, CLAP, DX, LV2
  bool bypassed = false;
  bool offline = false;
  std::string preset;
  std::vector<std::string> values;  // JS slider values
  std::vector<std::string> state;   // the plugin block's lines (base64 for VST)
};

struct Clip {
  std::string name;
  double position = 0, length = 0, offset = 0;
  double fadeIn = 0, fadeOut = 0;
  int fadeInShape = 0, fadeOutShape = 0;
  double gain = 1.0;
  double playrate = 1.0;
  std::vector<std::string> needsRender;  // "take FX", "playrate", "pitch", "stretch markers"
  int takes = 1;
  bool muted = false;
  std::string color;  // "#RRGGBB", item color else the track's
  std::shared_ptr<Source> source;
  double end() const { return position + length; }
  bool plays() const { return !muted && source && source->exists && source->frames > 0; }
};

struct Track {
  std::string name;
  int index = 0;
  std::vector<Clip> clips;
  int channels = 1;
  std::vector<Plugin> fx;
  bool isFolder = false;
  int depth = 0;
  std::string parent;
  std::string color;
};

struct NonAudio {
  std::string kind;  // MIDI, VIDEO, NOTES, SUBPROJECT, GENERATOR, OTHER
  std::string track;
  double position = 0, length = 0;
  std::string name;
};

struct Finding {
  std::string level;  // problem | warning | note | ok
  std::string title;
  std::string detail;
};

struct Session {
  std::string path, name;
  int sampleRate = 48000;
  double fps = 25.0;
  double offset = 0.0;
  std::vector<Track> tracks;
  std::vector<NonAudio> nonaudio;
  std::vector<Finding> findings;
  std::vector<std::pair<std::string, double>> videos;
  std::vector<Plugin> masterFx;
  std::string tc(double seconds) const;
};

// Read a .rpp file. Throws std::runtime_error when the file can't be read.
Session loadRpp(const std::string &path);
// Same from the project text (as REAPER hands it out); `path` locates relative media.
Session parseRpp(const std::string &text, const std::string &path);

// Split a track's playing clips into lanes one sequence can hold: crossfades stay in the lane,
// stacked clips go to the next lane, clips shorter than one sample are left out.
std::vector<std::vector<const Clip *>> lanes(const Track &t, int sampleRate);

// Sort non-audio items onto their own "NON-AUDIO - ..." tracks at the end of the project text.
// Returns the new text; `moved` gets "KIND count" pairs.
std::string sortNonAudio(const std::string &rppText, std::vector<std::pair<std::string, int>> *moved);

}  // namespace aafugo

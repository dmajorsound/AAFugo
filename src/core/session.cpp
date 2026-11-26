// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.

#include "session.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>

namespace aafugo {

// ------------------------------------------------------------------ RPP text -> tree
namespace {

struct Node;
struct Entry {
  std::vector<std::string> tok;  // a "KEY values" line
  Node *child = nullptr;         // or a <CHILD> block
};
struct Node {
  std::string tag;
  std::vector<std::string> args;
  std::vector<Entry> entries;
  std::vector<std::unique_ptr<Node>> owned;

  const std::vector<std::string> *first(const char *key) const {
    for (auto &e : entries)
      if (!e.child && !e.tok.empty() && e.tok[0] == key) return &e.tok;
    return nullptr;
  }
  const Node *child(const char *tag) const {
    for (auto &e : entries)
      if (e.child && e.child->tag == tag) return e.child;
    return nullptr;
  }
};

std::vector<std::string> tokenize(const std::string &s) {
  // REAPER quotes with " ' or ` and has no escapes
  std::vector<std::string> out;
  size_t i = 0, n = s.size();
  while (i < n) {
    while (i < n && (s[i] == ' ' || s[i] == '\t')) i++;
    if (i >= n) break;
    char q = s[i];
    if (q == '"' || q == '\'' || q == '`') {
      size_t j = s.find(q, i + 1);
      if (j == std::string::npos) j = n;
      out.push_back(s.substr(i + 1, j - i - 1));
      i = j + 1;
    } else {
      size_t j = i;
      while (j < n && s[j] != ' ' && s[j] != '\t') j++;
      out.push_back(s.substr(i, j - i));
      i = j;
    }
  }
  return out;
}

std::string trim(const std::string &s) {
  size_t a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return "";
  size_t b = s.find_last_not_of(" \t\r\n");
  return s.substr(a, b - a + 1);
}

std::unique_ptr<Node> parseTree(const std::string &text) {
  auto root = std::make_unique<Node>();
  root->tag = "ROOT";
  std::vector<Node *> stack{root.get()};
  std::istringstream in(text);
  std::string raw;
  while (std::getline(in, raw)) {
    std::string s = trim(raw);
    if (s.empty()) continue;
    if (s[0] == '<') {
      auto t = tokenize(s.substr(1));
      auto n = std::make_unique<Node>();
      if (!t.empty()) {
        n->tag = t[0];
        n->args.assign(t.begin() + 1, t.end());
      }
      Entry e;
      e.child = n.get();
      stack.back()->entries.push_back(e);
      Node *np = n.get();
      stack.back()->owned.push_back(std::move(n));
      stack.push_back(np);
    } else if (s == ">") {
      if (stack.size() > 1) stack.pop_back();
    } else {
      Entry e;
      e.tok = tokenize(s);
      stack.back()->entries.push_back(e);
    }
  }
  return root;
}

double num(const std::string &v, double def = 0.0) {
  char *e = nullptr;
  double d = std::strtod(v.c_str(), &e);
  return (e && e != v.c_str()) ? d : def;
}
double numAt(const std::vector<std::string> *t, size_t i, double def = 0.0) {
  return (t && t->size() > i) ? num((*t)[i], def) : def;
}

// a take: its lines and child blocks
struct Take {
  std::vector<const std::vector<std::string> *> lines;
  std::vector<const Node *> children;
  const std::vector<std::string> *get(const char *key) const {
    for (auto *l : lines)
      if (!l->empty() && (*l)[0] == key) return l;
    return nullptr;
  }
};

std::vector<Take> splitTakes(const Node &item, int *selected) {
  std::vector<Take> takes(1);
  *selected = 0;
  for (auto &e : item.entries) {
    if (e.child) {
      takes.back().children.push_back(e.child);
    } else if (!e.tok.empty() && e.tok[0] == "TAKE") {
      takes.emplace_back();
      if (e.tok.size() > 1 && e.tok[1] == "SEL") *selected = int(takes.size()) - 1;
    } else {
      takes.back().lines.push_back(&e.tok);
    }
  }
  return takes;
}

const std::set<std::string> kAudioSources = {"WAVE", "FLAC", "MP3", "VORBIS", "OPUS", "WAVPACK"};
const std::set<std::string> kPluginTags = {"VST", "VST3", "AU", "JS", "CLAP", "DX", "LV2", "VIDEO_EFFECT"};

std::string nonAudioKind(const std::string &k) {
  if (k == "MIDI") return "MIDI";
  if (k == "VIDEO") return "VIDEO";
  if (k == "RPP_PROJECT") return "SUBPROJECT";
  if (k == "CLICK") return "GENERATOR";
  if (k == "EMPTY" || k.empty()) return "NOTES";
  return "OTHER";
}

// REAPER custom color: native | 0x1000000. The .rpp keeps 0xBBGGRR on every platform
// (checked with a macOS session: "voice FX" PEAKCOL 16799752 is orange).
std::string nativeColor(const std::string &v) {
  long long c = (long long)num(v, 0);
  if (!(c & 0x1000000)) return "";
  c &= 0xFFFFFF;
  char b[8];
  std::snprintf(b, sizeof b, "#%02X%02X%02X", int(c & 255), int((c >> 8) & 255), int((c >> 16) & 255));
  return b;
}

std::vector<Plugin> parseFx(const Node &chain) {
  std::vector<Plugin> out;
  bool byp = false, off = false;
  for (auto &e : chain.entries) {
    if (!e.child) {
      if (e.tok.empty()) continue;
      if (e.tok[0] == "BYPASS") {
        byp = e.tok.size() > 1 && e.tok[1] == "1";
        off = e.tok.size() > 2 && e.tok[2] == "1";
      } else if (e.tok[0] == "PRESETNAME" && !out.empty()) {
        std::string p;
        for (size_t i = 1; i < e.tok.size(); i++) p += (i > 1 ? " " : "") + e.tok[i];
        out.back().preset = p;
      }
      continue;
    }
    const Node &n = *e.child;
    if (!kPluginTags.count(n.tag)) continue;
    Plugin p;
    p.type = n.tag;
    p.name = n.args.empty() ? n.tag : n.args[0];
    if (n.tag == "JS") p.name = "JS: " + p.name;
    p.bypassed = byp;
    p.offline = off;
    for (auto &l : n.entries) {
      if (l.child || l.tok.empty()) continue;
      p.state.push_back(l.tok[0]);
    }
    if (n.tag == "JS" && !n.entries.empty() && !n.entries[0].child)
      for (auto &v : n.entries[0].tok)
        if (v != "-") p.values.push_back(v);
    out.push_back(p);
    byp = off = false;
  }
  return out;
}

bool fileExists(const std::string &p) {
  std::ifstream f(p, std::ios::binary);
  return bool(f);
}

std::string dirName(const std::string &p) {
  size_t s = p.find_last_of("/\\");
  return s == std::string::npos ? "." : p.substr(0, s);
}
std::string baseName(const std::string &p) {
  size_t s = p.find_last_of("/\\");
  return s == std::string::npos ? p : p.substr(s + 1);
}
bool isAbs(const std::string &p) { return !p.empty() && (p[0] == '/' || (p.size() > 1 && p[1] == ':')); }

unsigned rd32(const unsigned char *b) { return b[0] | (b[1] << 8) | (b[2] << 16) | ((unsigned)b[3] << 24); }
unsigned rd16(const unsigned char *b) { return b[0] | (b[1] << 8); }

void readWav(Source &s) {
  std::ifstream f(s.path, std::ios::binary);
  unsigned char h[12];
  if (!f.read((char *)h, 12)) return;
  if ((std::memcmp(h, "RIFF", 4) && std::memcmp(h, "RF64", 4)) || std::memcmp(h + 8, "WAVE", 4)) return;
  long long dataSize = -1;
  for (;;) {
    unsigned char c[8];
    if (!f.read((char *)c, 8)) break;
    unsigned size = rd32(c + 4);
    if (!std::memcmp(c, "fmt ", 4)) {
      std::vector<unsigned char> d(size);
      f.read((char *)d.data(), size);
      if (size >= 16) {
        s.channels = rd16(&d[2]);
        s.sampleRate = (int)rd32(&d[4]);
        s.bits = rd16(&d[14]);
      }
      if (size & 1) f.seekg(1, std::ios::cur);
    } else if (!std::memcmp(c, "bext", 4)) {
      std::vector<unsigned char> d(size);
      f.read((char *)d.data(), size);
      if (size >= 346) s.timeRef = rd32(&d[338]) | ((unsigned long long)rd32(&d[342]) << 32);
      if (size & 1) f.seekg(1, std::ios::cur);
    } else if (!std::memcmp(c, "data", 4)) {
      dataSize = size;
      f.seekg(size + (size & 1), std::ios::cur);
    } else {
      f.seekg(size + (size & 1), std::ios::cur);
    }
  }
  if (dataSize >= 0 && s.channels && s.bits) s.frames = dataSize / (s.channels * (s.bits / 8));
}

}  // namespace

// ------------------------------------------------------------------ Session
std::string Session::tc(double seconds) const {
  double t = offset + seconds;
  int f = int(std::lround(fps));
  if (f <= 0) f = 25;
  long long fr = std::llround(t * fps);
  long long h = fr / (3600LL * f);
  fr %= 3600LL * f;
  long long m = fr / (60LL * f);
  fr %= 60LL * f;
  long long s = fr / f;
  fr %= f;
  char b[32];
  std::snprintf(b, sizeof b, "%02lld:%02lld:%02lld:%02lld", h, m, s, fr);
  return b;
}

std::vector<std::vector<const Clip *>> lanes(const Track &t, int sr) {
  std::vector<std::vector<const Clip *>> out;
  for (auto &c : t.clips) {
    if (!c.plays()) continue;
    if (std::llround(c.length * sr) < 1) continue;
    bool placed = false;
    for (auto &lane : out) {
      const Clip *last = lane.back();
      if (c.position >= last->end() - 1e-9) {
        lane.push_back(&c);
        placed = true;
        break;
      }
      if (c.end() > last->end() && (last->fadeOut > 0 || c.fadeIn > 0) &&
          (lane.size() < 2 || c.position >= lane[lane.size() - 2]->end())) {
        lane.push_back(&c);
        placed = true;
        break;
      }
    }
    if (!placed) out.push_back({&c});
  }
  return out;
}

static void preflight(Session &s, size_t nameLimit = 31) {
  auto &F = s.findings;
  auto plural = [](size_t n) { return n == 1 ? "" : "s"; };
  char b[256];
  std::vector<std::pair<const Track *, const Clip *>> offline, multi, muted, tiny, rnd;
  for (auto &t : s.tracks)
    for (auto &c : t.clips) {
      if (!c.source || !c.source->exists) offline.push_back({&t, &c});
      if (c.takes > 1) multi.push_back({&t, &c});
      if (c.muted) muted.push_back({&t, &c});
      if (std::llround(c.length * s.sampleRate) < 1) tiny.push_back({&t, &c});
      if (!c.needsRender.empty() && !c.muted) rnd.push_back({&t, &c});
    }
  auto where = [&](const std::vector<std::pair<const Track *, const Clip *>> &v) {
    std::string w;
    for (size_t i = 0; i < v.size() && i < 3; i++) w += (i ? ", " : "") + v[i].first->name + " " + s.tc(v[i].second->position);
    return w;
  };
  if (!offline.empty()) {
    std::snprintf(b, sizeof b, "%zu item%s with offline media", offline.size(), plural(offline.size()));
    F.push_back({"problem", b, where(offline)});
  }
  if (!multi.empty()) {
    std::snprintf(b, sizeof b, "%zu item%s with more than one take", multi.size(), plural(multi.size()));
    F.push_back({"warning", b, "Only the active take flies"});
  }
  if (!muted.empty()) {
    std::snprintf(b, sizeof b, "%zu muted item%s", muted.size(), plural(muted.size()));
    F.push_back({"warning", b, where(muted) + " - stays home"});
  }
  if (!tiny.empty()) {
    std::snprintf(b, sizeof b, "%zu empty item%s (shorter than a sample)", tiny.size(), plural(tiny.size()));
    F.push_back({"warning", b, where(tiny) + " - stays home"});
  }
  for (auto &t : s.tracks)
    if (t.name.size() > nameLimit) F.push_back({"warning", "Track name too long", "\"" + t.name + "\" will be shortened"});
  for (auto &t : s.tracks) {
    const Clip *prev = nullptr;
    for (auto &c : t.clips) {
      if (c.muted) continue;
      if (prev && c.position < prev->end() - 1e-9) {
        double ov = prev->end() - c.position;
        if (std::fabs(prev->fadeOut - ov) > 0.002 || std::fabs(c.fadeIn - ov) > 0.002) {
          std::snprintf(b, sizeof b, "%s %s: %.3f s", t.name.c_str(), s.tc(c.position).c_str(), ov);
          F.push_back({"note", "Crossfade made symmetric", b});
        }
      }
      prev = &c;
    }
  }
  std::string stacked;
  int ns = 0;
  for (auto &t : s.tracks)
    if (lanes(t, s.sampleRate).size() > 1 && ns++ < 4) stacked += (stacked.empty() ? "" : ", ") + t.name;
  if (ns) F.push_back({"note", "Stacked items go on extra tracks", stacked});
  size_t nfx = s.masterFx.size();
  for (auto &t : s.tracks) nfx += t.fx.size();
  if (nfx) {
    std::snprintf(b, sizeof b, "%zu plugins on tracks, folders and master", nfx);
    F.push_back({"note", b, "They don't travel in an AAF - listed with settings in the flight report"});
  }
  if (!rnd.empty()) {
    std::set<std::string> reasons;
    for (auto &p : rnd)
      for (auto &r : p.second->needsRender) reasons.insert(r);
    std::string rs;
    for (auto &r : reasons) rs += (rs.empty() ? "" : ", ") + r;
    std::snprintf(b, sizeof b, "%zu item%s will be rendered", rnd.size(), plural(rnd.size()));
    F.push_back({"note", b, rs});
  }
  if (!s.nonaudio.empty()) {
    std::map<std::string, int> kinds;
    for (auto &n : s.nonaudio) kinds[n.kind]++;
    std::string ks;
    for (auto &k : kinds) ks += (ks.empty() ? "" : ", ") + std::to_string(k.second) + " " + k.first;
    std::snprintf(b, sizeof b, "%zu non-audio item%s sorted out", s.nonaudio.size(), plural(s.nonaudio.size()));
    F.push_back({"note", b, ks});
  }
  std::set<int> other;
  for (auto &t : s.tracks)
    for (auto &c : t.clips)
      if (c.source && c.source->sampleRate && c.source->sampleRate != s.sampleRate) other.insert(c.source->sampleRate);
  if (!other.empty()) {
    std::string rs;
    for (int r : other) rs += (rs.empty() ? "" : ", ") + std::to_string(r) + " Hz";
    F.push_back({"problem", "Media at another sample rate", rs});
  } else {
    std::snprintf(b, sizeof b, "%d Hz - %g fps - starts %s", s.sampleRate, s.fps, s.tc(0).c_str());
    F.push_back({"ok", "Sample rate, frame rate and start TC", b});
  }
}

Session parseRpp(const std::string &text, const std::string &path) {
  auto tree = parseTree(text);
  Session s;
  s.path = path;
  std::string bn = baseName(path);
  s.name = bn.substr(0, bn.find_last_of('.'));
  std::string base = dirName(path);
  const Node *root = nullptr;
  for (auto &e : tree->entries)
    if (e.child) {
      root = e.child;
      break;
    }
  if (!root) return s;
  if (auto t = root->first("SAMPLERATE")) s.sampleRate = int(numAt(t, 1, 48000)) ? int(numAt(t, 1, 48000)) : 48000;
  if (auto t = root->first("PROJOFFS")) s.offset = numAt(t, 1);
  auto tm = root->first("TIMEMODE");
  if (tm && numAt(tm, 4) > 0)
    s.fps = numAt(tm, 4);
  else if (auto ss = root->first("SMPTESYNC"); ss && numAt(ss, 2) > 0)
    s.fps = numAt(ss, 2);
  if (auto m = root->child("MASTERFXLIST")) s.masterFx = parseFx(*m);

  std::map<std::string, std::shared_ptr<Source>> sources;
  int depth = 0;
  std::vector<std::string> parents;
  int ti = 0;
  for (auto &e : root->entries) {
    if (!e.child || e.child->tag != "TRACK") continue;
    const Node &tn = *e.child;
    Track tr;
    tr.index = ti++;
    auto nm = tn.first("NAME");
    tr.name = (nm && nm->size() > 1) ? (*nm)[1] : "Track " + std::to_string(tr.index + 1);
    if (auto pc = tn.first("PEAKCOL"); pc && pc->size() > 1) tr.color = nativeColor((*pc)[1]);
    if (auto fx = tn.child("FXCHAIN")) tr.fx = parseFx(*fx);
    tr.depth = depth;
    tr.parent = parents.empty() ? "" : parents.back();
    if (auto bus = tn.first("ISBUS")) {
      int a = int(numAt(bus, 1)), b = int(numAt(bus, 2, -1));
      if (a == 1) {
        tr.isFolder = true;
        depth++;
        parents.push_back(tr.name);
      } else if (a == 2) {
        for (int k = 0; k < -b && !parents.empty(); k++) {
          depth--;
          parents.pop_back();
        }
      }
    }
    for (auto &ie : tn.entries) {
      if (!ie.child || ie.child->tag != "ITEM") continue;
      const Node &it = *ie.child;
      int sel = 0;
      auto takes = splitTakes(it, &sel);
      const Take &t0 = takes[0];
      const Take &tk = takes[sel];
      double pos = numAt(t0.get("POSITION"), 1), len = numAt(t0.get("LENGTH"), 1);
      const Node *src = nullptr;
      for (auto *c : tk.children)
        if (c->tag == "SOURCE") {
          src = c;
          break;
        }
      std::string kind = (src && !src->args.empty()) ? src->args[0] : "";
      if (kind == "SECTION" && src->child("SOURCE")) {
        src = src->child("SOURCE");
        kind = src->args.empty() ? "" : src->args[0];
      }
      auto tnm = tk.get("NAME");
      if (!tnm) tnm = t0.get("NAME");
      std::string iname = (tnm && tnm->size() > 1) ? (*tnm)[1] : "";
      if (!kAudioSources.count(kind)) {
        bool notes = it.child("NOTES") != nullptr;
        NonAudio n{nonAudioKind(kind), tr.name, pos, len, iname};
        if (n.name.empty()) {
          std::string k = kind;
          for (auto &ch : k) ch = (char)std::tolower((unsigned char)ch);
          n.name = notes ? "notes" : k;
        }
        s.nonaudio.push_back(n);
        if (kind == "VIDEO" && src) {
          auto f = src->first("FILE");
          std::string vf = (f && f->size() > 1) ? (*f)[1] : "";
          s.videos.push_back({isAbs(vf) || vf.empty() ? vf : base + "/" + vf, pos});
        }
        continue;
      }
      Clip c;
      c.name = iname.empty() ? "clip" : iname;
      c.position = pos;
      c.length = len;
      c.offset = numAt(tk.get("SOFFS"), 1);
      // FADEIN shape len autolen ...: an auto-crossfade length (> 0) wins over the manual one
      auto eff = [](const std::vector<std::string> *v) {
        if (!v) return 0.0;
        double a = numAt(v, 3);
        return a > 0 ? a : numAt(v, 2);
      };
      auto fi = t0.get("FADEIN"), fo = t0.get("FADEOUT");
      c.fadeInShape = int(numAt(fi, 1));
      c.fadeIn = eff(fi);
      c.fadeOutShape = int(numAt(fo, 1));
      c.fadeOut = eff(fo);
      auto vp = tk.get("VOLPAN");
      c.gain = vp ? numAt(vp, 1, 1.0) : 1.0;
      auto mu = t0.get("MUTE");
      c.muted = mu && numAt(mu, 1) == 1;
      if (auto pr = tk.get("PLAYRATE")) {
        c.playrate = numAt(pr, 1, 1.0);
        if (std::fabs(c.playrate - 1.0) > 1e-9) c.needsRender.push_back("playrate");
        if (pr->size() > 3 && std::fabs(numAt(pr, 3)) > 1e-9) c.needsRender.push_back("pitch");
      }
      for (auto *ch : tk.children)
        if (ch->tag == "TAKEFX") {
          c.needsRender.push_back("take FX");
          break;
        }
      if (tk.get("SM")) c.needsRender.push_back("stretch markers");
      c.takes = int(takes.size());
      auto ic = t0.get("COLOR");
      c.color = (ic && ic->size() > 1) ? nativeColor((*ic)[1]) : "";
      if (c.color.empty()) c.color = tr.color;
      auto ff = src ? src->first("FILE") : nullptr;
      std::string f = (ff && ff->size() > 1) ? (*ff)[1] : "";
      std::string full = isAbs(f) ? f : base + "/" + f;
      if (!fileExists(full)) {
        // moved project: look next to the .rpp and in its media folders, like REAPER does
        std::string b2 = baseName(f);
        for (const char *d : {"", "media", "Media", "Audio", "audio"}) {
          std::string cand = base + "/" + (*d ? std::string(d) + "/" : "") + b2;
          if (fileExists(cand)) {
            full = cand;
            break;
          }
        }
      }
      auto &sp = sources[full];
      if (!sp) {
        sp = std::make_shared<Source>();
        sp->path = full;
        sp->exists = fileExists(full);
        std::string lo = full;
        for (auto &ch : lo) ch = (char)std::tolower((unsigned char)ch);
        sp->isWav = lo.size() > 4 && (lo.compare(lo.size() - 4, 4, ".wav") == 0 || lo.compare(lo.size() - 4, 4, ".bwf") == 0);
        if (sp->exists && sp->isWav) readWav(*sp);
      }
      c.source = sp;
      if (sp->channels) tr.channels = std::max(tr.channels, sp->channels);
      tr.clips.push_back(c);
    }
    std::stable_sort(tr.clips.begin(), tr.clips.end(), [](const Clip &a, const Clip &b) { return a.position < b.position; });
    s.tracks.push_back(std::move(tr));
  }
  preflight(s);
  return s;
}

Session loadRpp(const std::string &path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) throw std::runtime_error("can't read " + path);
  std::stringstream ss;
  ss << f.rdbuf();
  return parseRpp(ss.str(), path);
}

// ------------------------------------------------------------------ non-audio sorting
std::string sortNonAudio(const std::string &text, std::vector<std::pair<std::string, int>> *moved) {
  static const char *order[] = {"VIDEO", "MIDI", "NOTES", "SUBPROJECT", "GENERATOR", "OTHER"};
  static const std::map<std::string, std::string> trackName = {
      {"MIDI", "NON-AUDIO \xE2\x80\x93 MIDI"}, {"VIDEO", "NON-AUDIO \xE2\x80\x93 VIDEO"},
      {"NOTES", "NON-AUDIO \xE2\x80\x93 NOTES"}, {"SUBPROJECT", "NON-AUDIO \xE2\x80\x93 SUBPROJECTS"},
      {"GENERATOR", "NON-AUDIO \xE2\x80\x93 GENERATORS"}, {"OTHER", "NON-AUDIO \xE2\x80\x93 OTHER"}};
  std::vector<std::string> lines;
  {
    std::istringstream in(text);
    std::string l;
    while (std::getline(in, l)) lines.push_back(l);
  }
  std::map<std::string, std::vector<std::vector<std::string>>> buckets;
  std::vector<std::string> out;
  int depth = 0;
  bool inTrack = false;
  for (size_t i = 0; i < lines.size(); i++) {
    std::string s = trim(lines[i]);
    if (!s.empty() && s[0] == '<') {
      auto t = tokenize(s.substr(1));
      std::string tag = t.empty() ? "" : t[0];
      if (depth == 1 && tag == "TRACK") inTrack = true;
      if (depth == 2 && inTrack && tag == "ITEM") {
        std::vector<std::string> block;
        int d = 0;
        for (; i < lines.size(); i++) {
          block.push_back(lines[i]);
          std::string bs = trim(lines[i]);
          if (!bs.empty() && bs[0] == '<') d++;
          else if (bs == ">" && --d == 0) break;
        }
        std::string joined;
        for (auto &b : block) joined += b + "\n";
        auto tree = parseTree(joined);
        const Node *item = nullptr;
        for (auto &e : tree->entries)
          if (e.child) item = e.child;
        std::string kind;
        if (item) {
          int sel = 0;
          auto takes = splitTakes(*item, &sel);
          const Node *src = nullptr;
          for (auto *c : takes[sel].children)
            if (c->tag == "SOURCE") {
              src = c;
              break;
            }
          kind = (src && !src->args.empty()) ? src->args[0] : "";
          if (kind == "SECTION" && src->child("SOURCE") && !src->child("SOURCE")->args.empty())
            kind = src->child("SOURCE")->args[0];
        }
        if (kAudioSources.count(kind))
          out.insert(out.end(), block.begin(), block.end());
        else
          buckets[nonAudioKind(kind)].push_back(block);
        continue;
      }
      depth++;
    } else if (s == ">") {
      depth--;
      if (depth == 1) inTrack = false;
      if (depth == 0) {
        for (const char *k : order) {
          auto it = buckets.find(k);
          if (it == buckets.end()) continue;
          out.push_back("  <TRACK");
          out.push_back("    NAME \"" + trackName.at(k) + "\"");
          for (auto &b : it->second) out.insert(out.end(), b.begin(), b.end());
          out.push_back("  >");
          if (moved) moved->push_back({k, int(it->second.size())});
        }
      }
    }
    out.push_back(lines[i]);
  }
  std::string r;
  for (auto &l : out) r += l + "\n";
  return r;
}

}  // namespace aafugo

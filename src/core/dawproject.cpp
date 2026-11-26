// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.

#include "dawproject.h"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <set>

#include "zip.h"

namespace aafugo {

namespace {

const char *kColors[] = {"#4C93DC", "#E08A3C", "#5BAF6A", "#B06FC9", "#D9534F", "#3FB2B5", "#C9A43B", "#8A8F98"};

std::string esc(const std::string &v) {
  std::string o;
  for (char c : v) {
    switch (c) {
      case '&': o += "&amp;"; break;
      case '<': o += "&lt;"; break;
      case '>': o += "&gt;"; break;
      case '"': o += "&quot;"; break;
      default: o += c;
    }
  }
  return o;
}

// attribute list; pairs with an empty value are left out (like None in the prototype)
std::string attrs(std::initializer_list<std::pair<const char *, std::string>> kv) {
  std::string o;
  for (auto &p : kv) {
    if (p.second.empty()) continue;
    if (!o.empty()) o += " ";
    o += std::string(p.first) + "=\"" + esc(p.second) + "\"";
  }
  return o;
}

std::string f9(double v) {
  char b[64];
  std::snprintf(b, sizeof b, "%.9f", v);
  return b;
}

std::string baseName(const std::string &p) {
  size_t s = p.find_last_of("/\\");
  return s == std::string::npos ? p : p.substr(s + 1);
}

std::string b64decode(const std::string &in) {
  static int T[256];
  static bool init = false;
  if (!init) {
    for (int &t : T) t = -1;
    const char *a = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    for (int i = 0; i < 64; i++) T[(unsigned char)a[i]] = i;
    init = true;
  }
  std::string out;
  int val = 0, bits = -8;
  for (unsigned char c : in) {
    if (T[c] < 0) continue;
    val = (val << 6) + T[c];
    bits += 6;
    if (bits >= 0) {
      out.push_back(char((val >> bits) & 0xFF));
      bits -= 8;
    }
  }
  return out;
}

uint32_t le32(const std::string &s, size_t o) {
  auto *b = (const unsigned char *)s.data() + o;
  return b[0] | (b[1] << 8) | (b[2] << 16) | ((uint32_t)b[3] << 24);
}
void be32(std::string &s, uint32_t v) {
  s += char(v >> 24);
  s += char((v >> 16) & 255);
  s += char((v >> 8) & 255);
  s += char(v & 255);
}

// "VST: ReaEQ (Cockos)" -> ("ReaEQ", "Cockos")
void vstNames(const std::string &name, std::string *plain, std::string *vendor) {
  std::string n = name;
  size_t c = n.find(": ");
  if (c != std::string::npos && c < 6) n = n.substr(c + 2);
  vendor->clear();
  if (!n.empty() && n.back() == ')') {
    size_t o = n.rfind('(');
    if (o != std::string::npos) {
      *vendor = n.substr(o + 1, n.size() - o - 2);
      n = n.substr(0, o);
      while (!n.empty() && n.back() == ' ') n.pop_back();
    }
  }
  *plain = n;
}

}  // namespace

std::string vst2Fxp(const Plugin &p, unsigned *uniqueId) {
  if (p.type != "VST" || p.state.size() < 2) return "";
  std::string joined;
  for (size_t i = 0; i + 1 < p.state.size(); i++) joined += p.state[i];
  std::string raw = b64decode(joined), tail = b64decode(p.state.back());
  if (raw.size() < 12) return "";
  uint32_t uid = le32(raw, 0), magic = le32(raw, 4);
  if (magic != 0xFEED5EEE && magic != 0xFEED5EEF) return "";
  size_t o = 8;
  int32_t nin = (int32_t)le32(raw, o);
  o += 4 + 8 * (size_t)std::max(0, nin);
  if (o + 4 > raw.size()) return "";
  int32_t nout = (int32_t)le32(raw, o);
  o += 4 + 8 * (size_t)std::max(0, nout);
  if (o + 4 > raw.size()) return "";
  uint32_t size = le32(raw, o);
  o += 4 + 8;  // chunk size, then 8 bytes of flags
  if (o + size > raw.size()) return "";
  std::string chunk = raw.substr(o, size);
  std::string prg;
  size_t k = (!tail.empty() && tail[0] == 0) ? 1 : 0;
  for (; k < tail.size() && tail[k] && prg.size() < 27; k++) prg += tail[k];
  std::string body = "FPCh";
  be32(body, 1);
  be32(body, uid);
  be32(body, 1);
  be32(body, 1);
  prg.resize(28, '\0');
  body += prg;
  be32(body, size);
  body += chunk;
  std::string out = "CcnK";
  be32(out, (uint32_t)body.size());
  out += body;
  if (uniqueId) *uniqueId = uid;
  return out;
}

ExportSummary writeDawProject(const Session &s, const std::string &outPath) {
  ExportSummary sum;
  int idn = 0;
  auto nid = [&]() { return "id" + std::to_string(++idn); };
  const double t0 = s.offset;
  std::vector<std::string> X = {"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
                                "<Project version=\"1.0\">",
                                "  <Application name=\"AAFUGO\" version=\"0.1\"/>",
                                "  <Transport>"};
  X.push_back("    <Tempo " + attrs({{"max", "666"}, {"min", "20"}, {"unit", "bpm"}, {"value", "120"}, {"id", nid()}, {"name", "Tempo"}}) + "/>");
  X.push_back("    <TimeSignature denominator=\"4\" numerator=\"4\" id=\"" + nid() + "\"/>");
  X.push_back("  </Transport>");
  X.push_back("  <Structure>");
  std::string master = nid();
  struct TL {
    const Track *tr;
    std::vector<const Clip *> clips;
    std::string tid, vol;
  };
  std::vector<TL> tracks;
  std::vector<std::pair<std::string, std::string>> files;  // source path -> name in zip
  std::map<std::string, std::string> fileOf;
  std::vector<std::pair<std::string, std::string>> states;  // path in zip -> data

  auto devices = [&](const std::vector<Plugin> &fxl, const std::string &pad) {
    std::vector<std::string> out;
    for (auto &fx : fxl) {
      unsigned uid = 0;
      std::string data = vst2Fxp(fx, &uid);
      if (data.empty()) {
        sum.pluginsSkipped++;
        continue;
      }
      std::string plain, vendor;
      vstNames(fx.name, &plain, &vendor);
      std::string safe;
      for (char c : plain) safe += (std::isalnum((unsigned char)c) ? c : '_');
      while (!safe.empty() && safe.back() == '_') safe.pop_back();
      while (!safe.empty() && safe.front() == '_') safe.erase(0, 1);
      std::string path = "plugins/" + safe + "_" + std::to_string(states.size() + 1) + ".fxp";
      states.push_back({path, data});
      out.push_back(pad + "<Vst2Plugin " + attrs({{"deviceID", std::to_string(uid)}, {"deviceName", plain}, {"deviceRole", "audioFX"},
                                                  {"deviceVendor", vendor}, {"loaded", "true"}, {"id", nid()}, {"name", plain}}) + ">");
      out.push_back(pad + "  <Enabled value=\"" + std::string(fx.bypassed ? "false" : "true") + "\" id=\"" + nid() + "\" name=\"On/Off\"/>");
      out.push_back(pad + "  <State path=\"" + esc(path) + "\"/>");
      out.push_back(pad + "</Vst2Plugin>");
      sum.plugins++;
    }
    if (out.empty()) return out;
    std::string dp = pad.substr(0, pad.size() - 2);
    out.insert(out.begin(), dp + "<Devices>");
    out.push_back(dp + "</Devices>");
    return out;
  };
  auto channel = [&](const std::string &pad, const std::string &cid, int nch, const std::string &dest, const char *role,
                     const std::vector<Plugin> &fxl, const std::string &vol) {
    X.push_back(pad + "<Channel " + attrs({{"audioChannels", std::to_string(nch)}, {"destination", dest}, {"role", role},
                                           {"solo", "false"}, {"id", cid}}) + ">");
    for (auto &l : devices(fxl, pad + "    ")) X.push_back(l);
    X.push_back(pad + "  <Mute value=\"false\" id=\"" + nid() + "\" name=\"Mute\"/>");
    X.push_back(pad + "  <Pan max=\"1\" min=\"0\" unit=\"normalized\" value=\"0.5\" id=\"" + nid() + "\" name=\"Pan\"/>");
    X.push_back(pad + "  <Volume max=\"2\" min=\"0\" unit=\"linear\" value=\"1\" id=\"" + (vol.empty() ? nid() : vol) + "\" name=\"Volume\"/>");
    X.push_back(pad + "</Channel>");
  };

  // the track tree: folders become group tracks (contentType "tracks") with a submix channel
  std::vector<std::string> stack{master};
  int openDepth = 0;
  for (size_t i = 0; i < s.tracks.size(); i++) {
    const Track &tr = s.tracks[i];
    while (openDepth > tr.depth) {
      X.push_back("    " + std::string(2 * openDepth, ' ') + "</Track>");
      openDepth--;
      stack.pop_back();
    }
    std::string pad = "    " + std::string(2 * (tr.depth + 1), ' ');
    std::string tpad = pad.substr(0, pad.size() - 2);
    std::string color = tr.color.empty() ? kColors[i % 8] : tr.color;
    std::vector<const Clip *> clips;
    for (auto &c : tr.clips)
      if (c.plays()) clips.push_back(&c);
    if (tr.isFolder) {
      std::string tid = nid(), cid = nid();
      X.push_back(tpad + "<Track " + attrs({{"contentType", "tracks"}, {"loaded", "true"}, {"id", tid}, {"name", tr.name}, {"color", color}}) + ">");
      channel(pad, cid, 2, stack.back(), "submix", tr.fx, "");
      stack.push_back(cid);
      openDepth++;
      sum.folders++;
      continue;
    }
    if (clips.empty() && tr.fx.empty()) continue;
    std::string tid = nid(), cid = nid(), vol = nid();
    int nch = 0;
    for (auto *c : clips) nch = std::max(nch, c->source->channels);
    if (!nch) nch = 2;
    if (!clips.empty()) tracks.push_back({&tr, clips, tid, vol});
    X.push_back(tpad + "<Track " + attrs({{"contentType", "audio"}, {"loaded", "true"}, {"id", tid}, {"name", tr.name}, {"color", color}}) + ">");
    channel(pad, cid, nch, stack.back(), "regular", tr.fx, vol);
    X.push_back(tpad + "</Track>");
    sum.tracks++;
  }
  while (openDepth > 0) {
    X.push_back("    " + std::string(2 * openDepth, ' ') + "</Track>");
    openDepth--;
  }
  X.push_back("    <Track " + attrs({{"contentType", "audio"}, {"loaded", "true"}, {"id", nid()}, {"name", "Master"}}) + ">");
  channel("      ", master, 2, "", "master", s.masterFx, "");
  X.push_back("    </Track>");
  X.push_back("  </Structure>");
  X.push_back("  <Arrangement id=\"" + nid() + "\">");
  X.push_back("    <Lanes timeUnit=\"seconds\" id=\"" + nid() + "\">");
  std::set<std::string> used;
  for (auto &tl : tracks) {
    X.push_back("      <Lanes track=\"" + tl.tid + "\" id=\"" + nid() + "\">");
    X.push_back("        <Clips id=\"" + nid() + "\">");
    for (auto *c : tl.clips) {
      const Source &src = *c->source;
      if (!fileOf.count(src.path)) {
        std::string b = baseName(src.path), name = b;
        size_t dot = b.find_last_of('.');
        std::string stem = dot == std::string::npos ? b : b.substr(0, dot), ext = dot == std::string::npos ? "" : b.substr(dot);
        for (int n = 2; used.count(name); n++) name = stem + "_" + std::to_string(n) + ext;
        used.insert(name);
        fileOf[src.path] = name;
        files.push_back({src.path, name});
      }
      X.push_back("          <Clip " + attrs({{"time", f9(t0 + c->position)}, {"duration", f9(c->length)}, {"contentTimeUnit", "seconds"},
                                              {"playStart", f9(c->offset)}, {"fadeTimeUnit", "seconds"}, {"fadeInTime", f9(c->fadeIn)},
                                              {"fadeOutTime", f9(c->fadeOut)}, {"name", c->name}}) + ">");
      X.push_back("            <Audio " + attrs({{"channels", std::to_string(src.channels)}, {"sampleRate", std::to_string(src.sampleRate)},
                                                 {"duration", f9(src.duration())}, {"id", nid()}}) + ">");
      X.push_back("              <File path=\"" + esc("audio/" + fileOf[src.path]) + "\"/>");
      X.push_back("            </Audio>");
      X.push_back("          </Clip>");
      sum.clips++;
      sum.fades += (c->fadeIn > 0) + (c->fadeOut > 0);
    }
    X.push_back("        </Clips>");
    bool anyGain = false;
    for (auto *c : tl.clips) anyGain |= std::fabs(c->gain - 1) > 1e-6;
    if (anyGain) {
      X.push_back("        <Points id=\"" + nid() + "\" unit=\"linear\">");
      X.push_back("          <Target parameter=\"" + tl.vol + "\"/>");
      for (size_t k = 0; k < tl.clips.size(); k++) {
        const Clip *c = tl.clips[k];
        char b[160];
        std::snprintf(b, sizeof b, "          <RealPoint time=\"%.9f\" value=\"%.6f\" interpolation=\"hold\"/>", t0 + c->position, c->gain);
        X.push_back(b);
        const Clip *nx = k + 1 < tl.clips.size() ? tl.clips[k + 1] : nullptr;
        if (!nx || nx->position > c->end() + 1e-9) {
          std::snprintf(b, sizeof b, "          <RealPoint time=\"%.9f\" value=\"1\" interpolation=\"hold\"/>", t0 + c->end());
          X.push_back(b);
        }
        if (std::fabs(c->gain - 1) > 1e-6) sum.gains++;
      }
      X.push_back("        </Points>");
    }
    X.push_back("      </Lanes>");
  }
  X.push_back("    </Lanes>");
  X.push_back("  </Arrangement>");
  X.push_back("  <Scenes/>");
  X.push_back("</Project>");
  std::string xml;
  for (auto &l : X) xml += l + "\n";
  char m[512];
  std::snprintf(m, sizeof m, "  <Comment>Exported from REAPER with AAFUGO. Start %s, %d Hz, %g fps.</Comment>\n", s.tc(0).c_str(),
                s.sampleRate, s.fps);
  std::string meta = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<MetaData>\n  <Title>" + esc(s.name) +
                     "</Title>\n" + m + "</MetaData>\n";
  ZipWriter z(outPath);
  z.addData("project.xml", xml);
  z.addData("metadata.xml", meta);
  for (auto &st : states) z.addData(st.first, st.second);
  for (auto &f : files) z.addFile("audio/" + f.second, f.first);
  if (!z.close()) sum.error = z.error().empty() ? "write failed" : z.error();
  return sum;
}

}  // namespace aafugo

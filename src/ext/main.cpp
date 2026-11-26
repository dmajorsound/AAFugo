// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.
//
// REAPER extension entry point (version 0.1: no dialog yet).
//  * "AAFUGO: Export session..."  saves the project, shows the Pre-Flight list and writes the export
//    (DAWproject for Nuendo/Cubase, Studio One, Bitwig) into "<project folder>/AAFUGO export".
//  * "AAFUGO: Sort non-audio items onto their own tracks"  moves MIDI, video, empty / notes items
//    and other non-audio items onto "NON-AUDIO - ..." tracks (one undo step).

#include <algorithm>
#include <cstring>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

#include "../core/dawproject.h"
#include "../core/session.h"

#ifdef _WIN32
#include <windows.h>
#endif

#define REAPERAPI_IMPLEMENT
#define REAPERAPI_MINIMAL
#define REAPERAPI_WANT_plugin_register
#define REAPERAPI_WANT_AddExtensionsMainMenu
#define REAPERAPI_WANT_EnumProjects
#define REAPERAPI_WANT_Main_OnCommand
#define REAPERAPI_WANT_ShowMessageBox
#define REAPERAPI_WANT_CountTracks
#define REAPERAPI_WANT_GetTrack
#define REAPERAPI_WANT_CountTrackMediaItems
#define REAPERAPI_WANT_GetTrackMediaItem
#define REAPERAPI_WANT_GetActiveTake
#define REAPERAPI_WANT_GetMediaItemTake_Source
#define REAPERAPI_WANT_GetMediaSourceType
#define REAPERAPI_WANT_InsertTrackAtIndex
#define REAPERAPI_WANT_GetSetMediaTrackInfo_String
#define REAPERAPI_WANT_MoveMediaItemToTrack
#define REAPERAPI_WANT_Undo_BeginBlock2
#define REAPERAPI_WANT_Undo_EndBlock2
#define REAPERAPI_WANT_UpdateArrange
#define REAPERAPI_WANT_PreventUIRefresh
#define REAPERAPI_WANT_TrackList_AdjustWindows
#include "../../third_party/reaper-sdk/sdk/reaper_plugin.h"
#include "../../third_party/reaper-sdk/sdk/reaper_plugin_functions.h"

namespace fs = std::filesystem;

static int g_cmdExport = 0, g_cmdSort = 0;
static const char *kTitle = "AAFUGO";

// ---------------------------------------------------------------- export

static std::string preflightText(const aafugo::Session &s) {
  std::string t = "PRE-FLIGHT  " + s.name + "\n\n";
  for (auto &f : s.findings) {
    const char *mark = f.level == "problem" ? "[!] " : f.level == "warning" ? "[?] " : f.level == "ok" ? "[ok] " : "[i] ";
    t += mark + f.title + (f.detail.empty() ? "" : "\n      " + f.detail) + "\n";
  }
  return t;
}

static void exportSession() {
  char fn[4096] = "";
  EnumProjects(-1, fn, sizeof fn);
  if (!fn[0]) {
    ShowMessageBox("Save the project first. AAFUGO exports a saved REAPER project.", kTitle, 0);
    return;
  }
  Main_OnCommand(40026, 0);  // File: Save project
  aafugo::Session s;
  try {
    s = aafugo::loadRpp(fn);
  } catch (std::exception &e) {
    ShowMessageBox(e.what(), kTitle, 0);
    return;
  }
  std::string msg = preflightText(s) +
                    "\nThis version (0.1) exports DAWproject (Nuendo/Cubase, Studio One, Bitwig).\n"
                    "Items with FX, pitch or playrate go out unrendered for now. AAF follows.\n\nExport now?";
  if (ShowMessageBox(msg.c_str(), kTitle, 1) != 1) return;  // 1 = OK
  fs::path dir = fs::path(fn).parent_path() / "AAFUGO export";
  std::error_code ec;
  fs::create_directories(dir, ec);
  fs::path out = dir / (s.name + "_Nuendo-Cubase.dawproject");
  aafugo::ExportSummary r = aafugo::writeDawProject(s, out.string());
  if (!r.error.empty()) {
    ShowMessageBox(("Export failed: " + r.error).c_str(), kTitle, 0);
    return;
  }
  char b[512];
  snprintf(b, sizeof b, "%d clips, %d fades, %d clip gains, %d tracks, %d folders, %d plugins (%d left out).", r.clips, r.fades, r.gains,
           r.tracks, r.folders, r.plugins, r.pluginsSkipped);
  ShowMessageBox(("Cheers. Your session is on its way.\n\n" + out.string() + "\n\n" + b).c_str(), kTitle, 0);
}

// ---------------------------------------------------------------- non-audio sorting

static std::string kindOf(MediaItem *it) {
  MediaItem_Take *tk = GetActiveTake(it);
  if (!tk) return "NOTES";  // empty item
  PCM_source *src = GetMediaItemTake_Source(tk);
  if (!src) return "NOTES";
  char t[64] = "";
  GetMediaSourceType(src, t, sizeof t);
  std::string k = t;
  if (k == "WAVE" || k == "FLAC" || k == "MP3" || k == "VORBIS" || k == "OPUS" || k == "WAVPACK" || k == "SECTION") return "";
  if (k == "MIDI" || k == "MIDIPOOL") return "MIDI";
  if (k == "VIDEO") return "VIDEO";
  if (k == "RPP_PROJECT") return "SUBPROJECTS";
  if (k == "CLICK") return "GENERATORS";
  if (k == "EMPTY" || k.empty()) return "NOTES";
  return "OTHER";
}

static void sortNonAudio() {
  std::map<std::string, std::vector<MediaItem *>> found;
  int nt = CountTracks(nullptr);
  for (int i = 0; i < nt; i++) {
    MediaTrack *tr = GetTrack(nullptr, i);
    char name[256] = "";
    GetSetMediaTrackInfo_String(tr, "P_NAME", name, false);
    if (!strncmp(name, "NON-AUDIO", 9)) continue;  // sorted already
    for (int j = 0; j < CountTrackMediaItems(tr); j++) {
      MediaItem *it = GetTrackMediaItem(tr, j);
      std::string k = kindOf(it);
      if (!k.empty()) found[k].push_back(it);
    }
  }
  if (found.empty()) {
    ShowMessageBox("No non-audio items on the tracks.", kTitle, 0);
    return;
  }
  Undo_BeginBlock2(nullptr);
  PreventUIRefresh(1);
  std::string summary;
  for (const char *k : {"VIDEO", "MIDI", "NOTES", "SUBPROJECTS", "GENERATORS", "OTHER"}) {
    auto f = found.find(k);
    if (f == found.end()) continue;
    std::string tn = std::string("NON-AUDIO \xE2\x80\x93 ") + k;
    MediaTrack *dest = nullptr;
    for (int i = 0; i < CountTracks(nullptr) && !dest; i++) {
      char name[256] = "";
      GetSetMediaTrackInfo_String(GetTrack(nullptr, i), "P_NAME", name, false);
      if (tn == name) dest = GetTrack(nullptr, i);
    }
    if (!dest) {
      int at = CountTracks(nullptr);
      InsertTrackAtIndex(at, false);
      dest = GetTrack(nullptr, at);
      GetSetMediaTrackInfo_String(dest, "P_NAME", (char *)tn.c_str(), true);
    }
    for (MediaItem *it : f->second) MoveMediaItemToTrack(it, dest);
    summary += std::to_string(f->second.size()) + " " + k + "\n";
  }
  PreventUIRefresh(-1);
  TrackList_AdjustWindows(false);
  UpdateArrange();
  Undo_EndBlock2(nullptr, "AAFUGO: sort non-audio items", -1);
  ShowMessageBox(("Moved onto NON-AUDIO tracks:\n\n" + summary + "\nUndo brings them back.").c_str(), kTitle, 0);
}

// ---------------------------------------------------------------- actions and menu

static bool onAction(KbdSectionInfo *, int command, int, int, int, HWND) {
  if (command == g_cmdExport && g_cmdExport) {
    exportSession();
    return true;
  }
  if (command == g_cmdSort && g_cmdSort) {
    sortNonAudio();
    return true;
  }
  return false;
}

static void addItem(HMENU menu, int id, const char *text) {
  MENUITEMINFO mi;
  memset(&mi, 0, sizeof(mi));
  mi.cbSize = sizeof(mi);
  mi.fMask = MIIM_TYPE | MIIM_ID;
  mi.fType = MFT_STRING;
  mi.wID = (UINT)id;
  mi.dwTypeData = (char *)text;
  InsertMenuItem(menu, GetMenuItemCount(menu), TRUE, &mi);
}

static void menuHook(const char *menuId, void *menu, int flag) {
  if (flag != 0 || !menu || strcmp(menuId, "Main extensions")) return;
  if (g_cmdExport) addItem((HMENU)menu, g_cmdExport, "AAFUGO: Export session...");
  if (g_cmdSort) addItem((HMENU)menu, g_cmdSort, "AAFUGO: Sort non-audio items onto their own tracks");
}

extern "C" REAPER_PLUGIN_DLL_EXPORT int REAPER_PLUGIN_ENTRYPOINT(REAPER_PLUGIN_HINSTANCE, reaper_plugin_info_t *rec) {
  if (!rec) {
    plugin_register("-hookcommand2", (void *)onAction);
    plugin_register("-hookcustommenu", (void *)menuHook);
    return 0;
  }
  if (rec->caller_version != REAPER_PLUGIN_VERSION || !rec->GetFunc) return 0;
  if (REAPERAPI_LoadAPI(rec->GetFunc) != 0) return 0;
  static custom_action_register_t exp = {0, "DMAJORSOUND_AAFUGO_EXPORT", "AAFUGO: Export session...", nullptr};
  static custom_action_register_t srt = {0, "DMAJORSOUND_AAFUGO_SORT", "AAFUGO: Sort non-audio items onto their own tracks", nullptr};
  g_cmdExport = plugin_register("custom_action", &exp);
  g_cmdSort = plugin_register("custom_action", &srt);
  plugin_register("hookcommand2", (void *)onAction);
  AddExtensionsMainMenu();
  plugin_register("hookcustommenu", (void *)menuHook);
  return 1;
}

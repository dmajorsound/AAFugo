// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.

#include "zip.h"

namespace aafugo {

uint32_t crc32(uint32_t crc, const void *data, size_t n) {
  static uint32_t table[256];
  static bool init = false;
  if (!init) {
    for (uint32_t i = 0; i < 256; i++) {
      uint32_t c = i;
      for (int k = 0; k < 8; k++) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
      table[i] = c;
    }
    init = true;
  }
  crc = ~crc;
  auto *p = (const unsigned char *)data;
  for (size_t i = 0; i < n; i++) crc = table[(crc ^ p[i]) & 255] ^ (crc >> 8);
  return ~crc;
}

namespace {
void w16(std::ofstream &o, uint16_t v) {
  char b[2] = {char(v & 255), char(v >> 8)};
  o.write(b, 2);
}
void w32(std::ofstream &o, uint32_t v) {
  char b[4] = {char(v & 255), char((v >> 8) & 255), char((v >> 16) & 255), char(v >> 24)};
  o.write(b, 4);
}
}  // namespace

ZipWriter::ZipWriter(const std::string &path) : out_(path, std::ios::binary | std::ios::trunc) {
  if (!out_) {
    ok_ = false;
    err_ = "can't write " + path;
  }
}

ZipWriter::~ZipWriter() {
  if (!closed_) close();
}

void ZipWriter::header(const std::string &name, uint32_t crc, uint32_t size) {
  uint64_t off = (uint64_t)out_.tellp();
  if (off > 0xFFFFFFFFull) {
    ok_ = false;
    err_ = "archive larger than 4 GB";
    return;
  }
  entries_.push_back({name, crc, size, (uint32_t)off});
  w32(out_, 0x04034b50);
  w16(out_, 20);      // version needed
  w16(out_, 0x0800);  // UTF-8 names
  w16(out_, 0);       // stored
  w16(out_, 0);
  w16(out_, 0x21);  // date 1980-01-01
  w32(out_, crc);
  w32(out_, size);
  w32(out_, size);
  w16(out_, (uint16_t)name.size());
  w16(out_, 0);
  out_.write(name.data(), name.size());
}

void ZipWriter::addData(const std::string &name, const std::string &data) {
  if (!ok_) return;
  header(name, crc32(0, data.data(), data.size()), (uint32_t)data.size());
  out_.write(data.data(), data.size());
}

void ZipWriter::addFile(const std::string &name, const std::string &path) {
  if (!ok_) return;
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    ok_ = false;
    err_ = "can't read " + path;
    return;
  }
  std::vector<char> buf(1 << 20);
  uint32_t crc = 0;
  uint64_t size = 0;
  while (in.read(buf.data(), buf.size()) || in.gcount()) {
    crc = crc32(crc, buf.data(), (size_t)in.gcount());
    size += (uint64_t)in.gcount();
  }
  if (size > 0xFFFFFFFFull) {
    ok_ = false;
    err_ = path + " is larger than 4 GB";
    return;
  }
  header(name, crc, (uint32_t)size);
  in.clear();
  in.seekg(0);
  while (in.read(buf.data(), buf.size()) || in.gcount()) out_.write(buf.data(), in.gcount());
}

bool ZipWriter::close() {
  if (closed_) return ok_;
  closed_ = true;
  uint32_t cd = (uint32_t)out_.tellp();
  for (auto &e : entries_) {
    w32(out_, 0x02014b50);
    w16(out_, 20);
    w16(out_, 20);
    w16(out_, 0x0800);
    w16(out_, 0);
    w16(out_, 0);
    w16(out_, 0x21);
    w32(out_, e.crc);
    w32(out_, e.size);
    w32(out_, e.size);
    w16(out_, (uint16_t)e.name.size());
    w16(out_, 0);
    w16(out_, 0);
    w16(out_, 0);
    w16(out_, 0);
    w32(out_, 0);
    w32(out_, e.offset);
    out_.write(e.name.data(), e.name.size());
  }
  uint32_t cdSize = (uint32_t)out_.tellp() - cd;
  w32(out_, 0x06054b50);
  w16(out_, 0);
  w16(out_, 0);
  w16(out_, (uint16_t)entries_.size());
  w16(out_, (uint16_t)entries_.size());
  w32(out_, cdSize);
  w32(out_, cd);
  w16(out_, 0);
  out_.close();
  if (!out_) ok_ = false;
  return ok_;
}

}  // namespace aafugo

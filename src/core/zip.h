// AAFUGO - session export for REAPER
// Copyright (C) 2026 dmajorsound. Licensed under the GNU GPL v2 or later.
//
// A minimal zip writer: stored entries (no compression - audio doesn't compress anyway), CRC32,
// central directory. Entries up to 4 GB each, archive up to 4 GB.
#pragma once

#include <cstdint>
#include <fstream>
#include <string>
#include <vector>

namespace aafugo {

class ZipWriter {
 public:
  explicit ZipWriter(const std::string &path);
  ~ZipWriter();
  bool ok() const { return ok_; }
  const std::string &error() const { return err_; }
  void addData(const std::string &name, const std::string &data);
  void addFile(const std::string &name, const std::string &path);
  bool close();

 private:
  struct Entry {
    std::string name;
    uint32_t crc, size, offset;
  };
  void header(const std::string &name, uint32_t crc, uint32_t size);
  std::ofstream out_;
  std::vector<Entry> entries_;
  bool ok_ = true, closed_ = false;
  std::string err_;
};

uint32_t crc32(uint32_t crc, const void *data, size_t n);

}  // namespace aafugo

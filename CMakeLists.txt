cmake_minimum_required(VERSION 3.18)
project(AAFUGO VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
if(APPLE)
  set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "")
endif()

# ---- AAFUGO core: session model, non-audio sorting, writers
add_library(aafugo_core STATIC
  src/core/session.cpp
  src/core/zip.cpp
  src/core/dawproject.cpp)
if(WIN32)
  target_compile_definitions(aafugo_core PUBLIC NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)
endif()
if(MSVC)
  target_compile_options(aafugo_core PRIVATE /utf-8)
else()
  target_compile_options(aafugo_core PRIVATE -Wall -Wextra -Wno-unused-parameter)
endif()

add_executable(aafugo-cli src/cli/main.cpp)
target_link_libraries(aafugo-cli PRIVATE aafugo_core)

option(AAFUGO_BUILD_EXTENSION "Build the REAPER extension" ON)
if(AAFUGO_BUILD_EXTENSION)
  add_subdirectory(src/ext)
endif()

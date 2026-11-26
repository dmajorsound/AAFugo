# AAFUGO REAPER extension: reaper_aafugo.dll / .dylib / .so

set(EXT_SRC main.cpp)
set(SWELL ${PROJECT_SOURCE_DIR}/third_party/reaper-sdk/WDL/swell)
if(APPLE)
  list(APPEND EXT_SRC ${SWELL}/swell-modstub.mm)
  set_source_files_properties(${SWELL}/swell-modstub.mm PROPERTIES COMPILE_FLAGS "-x objective-c++")
elseif(UNIX)
  list(APPEND EXT_SRC ${SWELL}/swell-modstub-generic.cpp)
endif()
add_library(reaper_aafugo MODULE ${EXT_SRC})
target_link_libraries(reaper_aafugo PRIVATE aafugo_core)
# reaper_plugin.h finds "../WDL/swell/swell.h" next to it on mac/linux
target_include_directories(reaper_aafugo PRIVATE ${PROJECT_SOURCE_DIR}/third_party/reaper-sdk/sdk)
set_target_properties(reaper_aafugo PROPERTIES PREFIX "" CXX_VISIBILITY_PRESET hidden)

if(NOT WIN32)
  target_compile_definitions(reaper_aafugo PRIVATE SWELL_PROVIDED_BY_APP)
else()
  target_link_libraries(reaper_aafugo PRIVATE shell32 ole32 gdi32)
endif()

if(APPLE)
  set_target_properties(reaper_aafugo PROPERTIES SUFFIX ".dylib")
  target_link_options(reaper_aafugo PRIVATE -undefined dynamic_lookup)
  target_link_libraries(reaper_aafugo PRIVATE "-framework AppKit" "-framework CoreText" "-framework CoreGraphics")
elseif(UNIX)
  set_target_properties(reaper_aafugo PROPERTIES SUFFIX ".so")
  target_link_libraries(reaper_aafugo PRIVATE pthread dl)
endif()


cmake_minimum_required(VERSION 3.20)
project(z8_openxlsx LANGUAGES C CXX)

include(FetchContent)
set(OPENXLSX_CREATE_DOCS OFF CACHE BOOL "" FORCE)
set(OPENXLSX_BUILD_SAMPLES OFF CACHE BOOL "" FORCE)
set(OPENXLSX_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(OPENXLSX_BUILD_BENCHMARKS OFF CACHE BOOL "" FORCE)
set(OPENXLSX_ENABLE_LTO OFF CACHE BOOL "" FORCE)
set(OPENXLSX_ENABLE_LIBZIP OFF CACHE BOOL "" FORCE)
set(OPENXLSX_MONOLITHIC_LIBRARY OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

FetchContent_Declare(openxlsx
    GIT_REPOSITORY https://github.com/troldal/OpenXLSX.git
    GIT_TAG 2eb596ac69d5ef8c1a1be1de8ee481b5ce39baea)
FetchContent_MakeAvailable(openxlsx)

add_library(z8_openxlsx SHARED bridge.cpp)
target_compile_features(z8_openxlsx PRIVATE cxx_std_17)
target_link_libraries(z8_openxlsx PRIVATE OpenXLSX::OpenXLSX)
if(TARGET miniz::miniz)
    target_link_libraries(z8_openxlsx PRIVATE miniz::miniz)
elseif(TARGET miniz)
    target_link_libraries(z8_openxlsx PRIVATE miniz)
else()
    message(FATAL_ERROR "OpenXLSX miniz target is unavailable")
endif()
set_target_properties(z8_openxlsx PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

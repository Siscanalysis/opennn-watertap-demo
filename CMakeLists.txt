# The OpenNN trainers of the toys: model/ro_surrogate.exe and bsm2_steady/model/bsm2_surrogate.exe.
#
#   build_surrogates.bat                    (Windows: finds Visual Studio and runs the two lines below)
#   cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
#   cmake --build build
#
# OpenNN is built with them, from OPENNN_SOURCE_DIR when it names an OpenNN source tree, and otherwise
# from GitHub at OPENNN_COMMIT. Linking OpenNN's own target gives the trainers the compile options the
# library was built with (Eigen alignment and threading, OpenMP, the instruction set).

cmake_minimum_required(VERSION 3.24)
project(opennn_watertap_trainers LANGUAGES CXX)

set(OPENNN_SOURCE_DIR "" CACHE PATH "An OpenNN source tree; empty downloads OPENNN_COMMIT from GitHub")
# OpenNN 26.0.3 (master, 2026-10-23).
set(OPENNN_COMMIT "ad4dd0759b072cd1921fc59e3fc6c632146c0091" CACHE STRING "OpenNN commit downloaded when OPENNN_SOURCE_DIR is empty")

# The library only: no tests, examples, benchmarks, CUDA or install rules.
set(OpenNN_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(OpenNN_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(OpenNN_BUILD_BENCHMARKS OFF CACHE BOOL "" FORCE)
set(OpenNN_DISABLE_CUDA ON CACHE BOOL "" FORCE)
set(OpenNN_INSTALL OFF CACHE BOOL "" FORCE)

if(OPENNN_SOURCE_DIR)
    add_subdirectory("${OPENNN_SOURCE_DIR}" opennn)
else()
    include(FetchContent)
    FetchContent_Declare(opennn URL "https://github.com/Artelnics/opennn/archive/${OPENNN_COMMIT}.tar.gz")
    FetchContent_MakeAvailable(opennn)
endif()

add_executable(ro_surrogate model/main.cpp)
add_executable(bsm2_surrogate bsm2_steady/model/main.cpp)

foreach(trainer IN ITEMS ro_surrogate bsm2_surrogate)
    target_link_libraries(${trainer} PRIVATE opennn)
endforeach()

# Next to their sources, where the pipelines look for them, whatever the configuration.
set_target_properties(ro_surrogate PROPERTIES RUNTIME_OUTPUT_DIRECTORY "$<1:${CMAKE_CURRENT_SOURCE_DIR}/model>")
set_target_properties(bsm2_surrogate PROPERTIES RUNTIME_OUTPUT_DIRECTORY "$<1:${CMAKE_CURRENT_SOURCE_DIR}/bsm2_steady/model>")

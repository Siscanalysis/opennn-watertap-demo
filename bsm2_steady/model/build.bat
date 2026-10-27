@echo off
rem Builds bsm2_surrogate.exe against a prebuilt OpenNN static library (no CMake).
rem The library and these headers must come from the same commit; this toy was
rem built against OpenNN dev 31da51dbd (opennn-build\verify-cpu, MSVC 14.39, Release).
rem Override OPENNN_SRC, OPENNN_BUILD or EIGEN_SRC to point at another tree, and OPENNN_DEPS
rem (default %OPENNN_BUILD%\_deps) or OPENNN_LIB (default %OPENNN_BUILD%\opennn\opennn.lib)
rem when that build keeps them elsewhere.

setlocal
if "%OPENNN_SRC%"=="" set OPENNN_SRC=%USERPROFILE%\Documents\opennn
if "%OPENNN_BUILD%"=="" set OPENNN_BUILD=%USERPROFILE%\Documents\opennn-build\verify-cpu
if "%OPENNN_DEPS%"=="" set OPENNN_DEPS=%OPENNN_BUILD%\_deps
if "%OPENNN_LIB%"=="" set OPENNN_LIB=%OPENNN_BUILD%\opennn\opennn.lib
if "%EIGEN_SRC%"=="" set EIGEN_SRC=C:\rcb\_deps\eigen-src

call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1

pushd "%~dp0"

cl /nologo /TP -DEIGEN_MAX_ALIGN_BYTES=64 -DEIGEN_MPL2_ONLY -DEIGEN_NO_DEBUG -DEIGEN_USE_THREADS ^
   -DOPENNN_HAS_PARALLEL_ALGORITHMS ^
   -I"%OPENNN_SRC%" -I"%OPENNN_DEPS%\opennn_zlib-build" -I"%OPENNN_DEPS%\opennn_zlib-src" ^
   -I"%EIGEN_SRC%" -external:I"%OPENNN_DEPS%\opennn_libjpeg_turbo-install\include" -external:W0 ^
   /DWIN32 /D_WINDOWS /EHsc /O2 /Ob2 /DNDEBUG -std:c++20 -MD /arch:AVX2 -openmp:experimental ^
   main.cpp /Fe:bsm2_surrogate.exe ^
   /link "%OPENNN_LIB%" ws2_32.lib "%OPENNN_DEPS%\opennn_zlib-build\zs.lib" ^
   "%OPENNN_DEPS%\opennn_libjpeg_turbo-install\lib\jpeg-static.lib"

set RESULT=%ERRORLEVEL%
if exist main.obj del main.obj
popd
exit /b %RESULT%

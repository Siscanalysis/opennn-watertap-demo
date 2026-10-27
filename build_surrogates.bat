@echo off
rem Builds the OpenNN trainers from zero: model\ro_surrogate.exe and bsm2_steady\model\bsm2_surrogate.exe.
rem OpenNN is downloaded from GitHub (the commit in CMakeLists.txt) and built with them, unless
rem OPENNN_SOURCE_DIR names an OpenNN source tree. Needs Visual Studio 2022 or later, or its Build
rem Tools, with the "Desktop development with C++" workload, which brings CMake and Ninja. The first
rem build takes about 15 minutes, most of it OpenNN; later builds redo only what changed.
rem
rem   build_surrogates.bat [--target ro_surrogate or bsm2_surrogate]
rem
rem BUILD_DIR (default .\build) holds the build; use another one for another OpenNN.

setlocal
set "ROOT=%~dp0"
if "%BUILD_DIR%"=="" set "BUILD_DIR=%ROOT%build"

rem In a developer prompt the compiler is already there; otherwise find Visual Studio.
where cl >nul 2>nul
if not errorlevel 1 goto :tools
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto :novs
set "VS="
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VS=%%I"
if "%VS%"=="" goto :novs
rem Visual Studio's environment script looks for vswhere on PATH.
set "PATH=%PATH%;%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 goto :novs

:tools
where cmake >nul 2>nul
if errorlevel 1 goto :nocmake
where ninja >nul 2>nul
if errorlevel 1 goto :nocmake

cmake -S "%ROOT%." -B "%BUILD_DIR%" -G Ninja -DCMAKE_BUILD_TYPE=Release "-DOPENNN_SOURCE_DIR=%OPENNN_SOURCE_DIR%"
if errorlevel 1 exit /b 1
cmake --build "%BUILD_DIR%" %*
exit /b %ERRORLEVEL%

:novs
echo Visual Studio with the C++ compiler was not found. Install Visual Studio 2022 or later, or the
echo Build Tools for Visual Studio, with the "Desktop development with C++" workload; or run this
echo from an "x64 Native Tools Command Prompt".
exit /b 1

:nocmake
echo CMake or Ninja was not found. Add "C++ CMake tools for Windows" to the Visual Studio
echo installation (part of "Desktop development with C++"), or put CMake 3.24+ and Ninja on PATH.
exit /b 1

@echo off
rem Builds ro_surrogate.exe here, with OpenNN, through the CMake project at the top of the
rem repository: see build_surrogates.bat there (OPENNN_SOURCE_DIR, BUILD_DIR).
call "%~dp0..\build_surrogates.bat" --target ro_surrogate
exit /b %ERRORLEVEL%

@echo off
rem Starts the local WaterTAP simulator service and opens the dashboard in the browser.
rem Close this window to stop it. The page's "Start WaterTAP" button runs this file with
rem --from-page (then no new browser tab opens); other options go to simulator\server.py
rem (--no-browser, --workers-bsm2=N, --workers-ro=N). Uses the Python environment that
rem ..\setup.bat set up; set PYTHON to another environment's python.exe to use that one instead.

setlocal EnableExtensions
title WaterTAP simulator
set "OPTIONS=%*"
if /i "%~1"=="--from-page" set "OPTIONS=--no-browser"
call :find_python
if defined PYTHON goto run

echo The WaterTAP environment is not set up on this computer yet.
echo setup.bat in the project folder installs it once (about 1 GB).
if /i not "%~1"=="--from-page" goto ask_setup
start "WaterTAP setup" "%~dp0..\setup.bat"
exit /b 1
:ask_setup
choice /c YN /m "Run setup.bat now"
if errorlevel 2 exit /b 1
call "%~dp0..\setup.bat" --no-pause
call :find_python
if defined PYTHON goto run
echo Setup did not finish; see the messages above.
pause
exit /b 1

:run
"%PYTHON%" -B "%~dp0simulator\server.py" 8765 %OPTIONS%
if errorlevel 1 pause
exit /b

:find_python
if defined PYTHON if exist "%PYTHON%" exit /b 0
set "PYTHON="
if exist "%~dp0simulator\python_path.txt" set /p PYTHON=<"%~dp0simulator\python_path.txt"
if defined PYTHON if exist "%PYTHON%" exit /b 0
set "PYTHON="
for %%P in ("%USERPROFILE%\miniforge3\envs\watertap\python.exe" "%SystemDrive%\miniforge3\envs\watertap\python.exe" "%USERPROFILE%\miniconda3\envs\watertap\python.exe" "%USERPROFILE%\anaconda3\envs\watertap\python.exe" "%LOCALAPPDATA%\miniforge3\envs\watertap\python.exe" "%ProgramData%\miniforge3\envs\watertap\python.exe") do if not defined PYTHON if exist %%P set "PYTHON=%%~P"
exit /b 0

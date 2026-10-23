@echo off
rem Starts the local WaterTAP simulator service and opens the dashboard in the browser.
rem Needs the "watertap" conda environment (see ..\README.md). Close this window to stop it.
rem Set PYTHON to that environment's python.exe if it is not found in the usual places.

setlocal
if not "%PYTHON%"=="" goto run
for %%P in ("%USERPROFILE%\miniforge3\envs\watertap\python.exe" "%USERPROFILE%\miniconda3\envs\watertap\python.exe" "%USERPROFILE%\anaconda3\envs\watertap\python.exe" "%LOCALAPPDATA%\miniforge3\envs\watertap\python.exe" "%ProgramData%\miniforge3\envs\watertap\python.exe") do if exist %%P (set "PYTHON=%%~P" & goto run)
where conda >nul 2>nul
if %ERRORLEVEL%==0 (
  conda run --no-capture-output -n watertap python -B "%~dp0simulator\server.py" 8765
  goto :eof
)
echo Could not find the "watertap" conda environment.
echo Create it as described in ..\README.md, or set PYTHON to its python.exe and run this again.
pause
exit /b 1

:run
"%PYTHON%" -B "%~dp0simulator\server.py" 8765

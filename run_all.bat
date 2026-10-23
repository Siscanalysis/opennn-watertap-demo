@echo off
rem Full pipeline: WaterTAP dataset -> OpenNN surrogate -> response optimization -> WaterTAP check.
rem Needs the "watertap" conda environment (see README.md) and the OpenNN build named in model\build.bat.

setlocal
if "%PYTHON%"=="" set PYTHON=%USERPROFILE%\miniforge3\envs\watertap\python.exe
set ROOT=%~dp0.

"%PYTHON%" "%ROOT%\generate_dataset.py" 1000 6 || exit /b 1
call "%ROOT%\model\build.bat" || exit /b 1
"%ROOT%\model\ro_surrogate.exe" train "%ROOT%" || exit /b 1
"%ROOT%\model\ro_surrogate.exe" optimize "%ROOT%" || exit /b 1
"%PYTHON%" "%ROOT%\verify_optima.py" 4 || exit /b 1
"%PYTHON%" "%ROOT%\plots.py" 4 || exit /b 1

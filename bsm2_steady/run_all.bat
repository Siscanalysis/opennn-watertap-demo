@echo off
rem Full pipeline: WaterTAP steady-state BSM2 dataset -> OpenNN surrogate -> response optimization -> WaterTAP check.
rem Needs the "watertap" conda environment (see ..\README.md) and the OpenNN build named in model\build.bat.

setlocal
if "%PYTHON%"=="" set PYTHON=%USERPROFILE%\miniforge3\envs\watertap\python.exe
set ROOT=%~dp0.

"%PYTHON%" "%ROOT%\generate_dataset.py" 800 6 20 || exit /b 1
call "%ROOT%\model\build.bat" || exit /b 1
"%ROOT%\model\bsm2_surrogate.exe" train "%ROOT%" || exit /b 1
"%ROOT%\model\bsm2_surrogate.exe" optimize "%ROOT%" || exit /b 1
"%PYTHON%" "%ROOT%\verify_optima.py" 6 || exit /b 1
"%PYTHON%" "%ROOT%\plots.py" || exit /b 1

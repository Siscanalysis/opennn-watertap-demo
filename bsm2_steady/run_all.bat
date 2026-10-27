@echo off
rem Full pipeline: WaterTAP steady-state BSM2 dataset -> OpenNN surrogate -> response optimization -> WaterTAP check.
rem Needs the environment ..\setup.bat creates (its python.exe is in ..\to_show\simulator\python_path.txt;
rem set PYTHON to use another). model\build.bat builds the OpenNN trainer (..\build_surrogates.bat).

setlocal
set ROOT=%~dp0.
if "%PYTHON%"=="" if exist "%ROOT%\..\to_show\simulator\python_path.txt" set /p PYTHON=<"%ROOT%\..\to_show\simulator\python_path.txt"
if "%PYTHON%"=="" set PYTHON=%USERPROFILE%\miniforge3\envs\watertap\python.exe

"%PYTHON%" "%ROOT%\generate_dataset.py" 800 6 20 || exit /b 1
call "%ROOT%\model\build.bat" || exit /b 1
"%ROOT%\model\bsm2_surrogate.exe" train "%ROOT%" || exit /b 1
"%ROOT%\model\bsm2_surrogate.exe" optimize "%ROOT%" || exit /b 1
"%PYTHON%" "%ROOT%\verify_optima.py" 6 || exit /b 1
"%PYTHON%" "%ROOT%\plots.py" || exit /b 1

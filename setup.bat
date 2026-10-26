@echo off
rem One-time setup of the demo on Windows. Running it again only repairs what is missing.
rem   1. The Python environment "watertap" (WaterTAP 1.8.0, IDAES 2.13) from environment.yml.
rem      Without conda on this computer, Miniforge is installed first, for this user only.
rem   2. The IDAES solvers (IPOPT), if missing.
rem   3. The page's "Start WaterTAP" button: an opennn-watertap: link, registered for this user,
rem      that runs to_show\start_simulator.bat from this folder.
rem   4. A check that both WaterTAP models build and solve.
rem Options:   --yes        answer yes to every question (for scripts and agents)
rem            --no-check   skip step 4
rem            --no-pause   do not wait for a key at the end
rem            --uninstall  remove the button's registration (the environment stays)
rem Variables: ENV_NAME (default watertap), MINIFORGE_DIR (where Miniforge goes, default
rem            %USERPROFILE%\miniforge3), PYTHON (an existing environment's python.exe to use).

setlocal EnableExtensions
set "ROOT=%~dp0"
set "KEY=HKCU\Software\Classes\opennn-watertap"
set "YES="
set "CHECK=1"
set "PAUSE=1"
set "UNINSTALL="
for %%A in (%*) do (
  if /i "%%~A"=="--yes" set "YES=1"
  if /i "%%~A"=="--no-check" set "CHECK="
  if /i "%%~A"=="--no-pause" set "PAUSE="
  if /i "%%~A"=="--uninstall" set "UNINSTALL=1"
)
if defined YES set "PAUSE="
if defined UNINSTALL goto uninstall
if not defined ENV_NAME set "ENV_NAME=watertap"

echo.
echo [1/4] Python environment "%ENV_NAME%"
call :find_env
if defined PYTHON goto have_env
call :find_conda
if not defined CONDA call :install_miniforge
if not defined CONDA goto no_conda
echo       Creating it with %CONDA%
echo       (downloads about 700 MB and takes a few minutes)
call "%CONDA%" env create -n "%ENV_NAME%" -f "%ROOT%environment.yml"
if not errorlevel 1 goto env_created
rem Miniforge 26.9 installs conda-launchers without the file hashes that its conda needs to create
rem an environment with pip; reinstalling that package repairs it.
echo       Repairing conda (reinstalling conda-launchers) and trying again
call "%CONDA%" install -n base -y --force-reinstall conda-launchers
call "%CONDA%" env remove -n "%ENV_NAME%" -y >nul 2>nul
call "%CONDA%" env create -n "%ENV_NAME%" -f "%ROOT%environment.yml"
if errorlevel 1 goto env_failed
:env_created
call :find_env
if not defined PYTHON goto env_failed
:have_env
echo       %PYTHON%

echo.
echo [2/4] Solvers
call :has_ipopt
if not errorlevel 1 goto have_solvers
echo       Downloading the IDAES solvers (about 110 MB)
for %%I in ("%PYTHON%") do set "PYDIR=%%~dpI"
"%PYDIR%Scripts\idaes.exe" get-extensions
call :has_ipopt
if errorlevel 1 goto solvers_failed
:have_solvers
echo       IPOPT found

echo.
echo [3/4] The page's Start WaterTAP button
>"%ROOT%to_show\simulator\python_path.txt" echo %PYTHON%
reg add "%KEY%" /ve /d "URL:OpenNN WaterTAP simulator" /f >nul
reg add "%KEY%" /v "URL Protocol" /d "" /f >nul
reg add "%KEY%\shell\open" /v "FriendlyAppName" /d "OpenNN WaterTAP simulator" /f >nul
reg add "%KEY%\shell\open\command" /ve /d "\"%SystemRoot%\System32\cmd.exe\" /c start \"WaterTAP simulator\" /min \"%ROOT%to_show\start_simulator.bat\" --from-page" /f >nul
if errorlevel 1 goto register_failed
echo       It now starts %ROOT%to_show\start_simulator.bat

echo.
if not defined CHECK goto finished
echo [4/4] Checking WaterTAP: both models are built and solve one operating point each (about two minutes)
"%PYTHON%" -B "%ROOT%to_show\simulator\server.py" --check
if errorlevel 1 goto check_failed

:finished
echo.
echo Setup complete. To run the demo:
echo   - double-click start_demo.bat: it starts the simulator and opens the page; or
echo   - open to_show\water_treatment_hmi.html and press Start WaterTAP (the browser asks once).
if defined PAUSE pause
exit /b 0

:no_conda
echo.
echo No conda was found and Miniforge was not installed. Install Miniforge from
echo https://github.com/conda-forge/miniforge and run setup.bat again.
goto failed
:env_failed
echo.
echo Creating the environment failed; see the messages above. Run setup.bat again to retry.
goto failed
:solvers_failed
echo.
echo The IDAES solvers could not be installed; see the messages above.
goto failed
:register_failed
echo.
echo The Start WaterTAP button could not be registered; start_demo.bat still works.
goto failed
:check_failed
echo.
echo WaterTAP did not solve; see the messages above.
:failed
if defined PAUSE pause
exit /b 1

:uninstall
reg delete "%KEY%" /f >nul 2>nul
del "%ROOT%to_show\simulator\python_path.txt" >nul 2>nul
echo The Start WaterTAP button is no longer registered. The Python environment stays;
echo remove it with: conda env remove -n watertap
if defined PAUSE pause
exit /b 0

rem ------------------------------------------------------------------ subroutines

:find_env
rem PYTHON = the environment's python.exe, if the environment exists.
if defined PYTHON if exist "%PYTHON%" exit /b 0
set "PYTHON="
for %%C in ("%MINIFORGE_DIR%" "%USERPROFILE%\miniforge3" "%SystemDrive%\miniforge3" "%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniforge3" "%ProgramData%\miniforge3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3" "%USERPROFILE%\.conda") do if not defined PYTHON if exist "%%~C\envs\%ENV_NAME%\python.exe" set "PYTHON=%%~C\envs\%ENV_NAME%\python.exe"
if defined PYTHON exit /b 0
call :find_conda
if not defined CONDA exit /b 0
for /f "usebackq delims=" %%P in (`call "%CONDA%" run -n "%ENV_NAME%" python -c "import sys; print(sys.executable)" 2^>nul`) do set "PYTHON=%%P"
if defined PYTHON if not exist "%PYTHON%" set "PYTHON="
exit /b 0

:find_conda
rem CONDA = a conda executable, if one is installed.
set "CONDA="
for %%C in ("%MINIFORGE_DIR%" "%USERPROFILE%\miniforge3" "%SystemDrive%\miniforge3" "%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniforge3" "%ProgramData%\miniforge3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3") do if not defined CONDA if exist "%%~C\Scripts\conda.exe" set "CONDA=%%~C\Scripts\conda.exe"
if defined CONDA exit /b 0
for /f "delims=" %%C in ('where conda.exe 2^>nul') do if not defined CONDA set "CONDA=%%C"
if defined CONDA exit /b 0
for /f "delims=" %%C in ('where conda.bat 2^>nul') do if not defined CONDA set "CONDA=%%C"
exit /b 0

:has_ipopt
"%PYTHON%" -c "import sys, idaes, pyomo.environ as pe; sys.exit(0 if pe.SolverFactory('ipopt').available(exception_flag=False) else 1)" >nul 2>nul
exit /b %errorlevel%

:install_miniforge
rem The installer refuses folders with spaces or special characters in their path.
set "MF=%USERPROFILE%\miniforge3"
if not "%MF%"=="%MF: =%" set "MF=%SystemDrive%\miniforge3"
if defined MINIFORGE_DIR set "MF=%MINIFORGE_DIR%"
echo       No conda on this computer. WaterTAP is installed with Miniforge (conda from
echo       conda-forge, about 150 MB to download), for this user only, in %MF%
if defined YES goto install_miniforge_now
choice /c YN /m "      Install Miniforge now"
if errorlevel 2 exit /b 0
:install_miniforge_now
set "MF_EXE=%TEMP%\Miniforge3-Windows-x86_64.exe"
curl.exe -L --fail --progress-bar -o "%MF_EXE%" https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe
if errorlevel 1 exit /b 0
echo       Installing Miniforge (a minute or two)
start "" /wait "%MF_EXE%" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S /D=%MF%
set "MF_EXIT=%errorlevel%"
del "%MF_EXE%" >nul 2>nul
if exist "%MF%\Scripts\conda.exe" set "CONDA=%MF%\Scripts\conda.exe"
if defined CONDA exit /b 0
echo       The Miniforge installer stopped (exit code %MF_EXIT%). Its folder needs a plain path,
echo       without spaces or special characters: set MINIFORGE_DIR to one and run setup.bat again.
exit /b 0

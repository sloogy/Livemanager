@echo off
setlocal
cd /d "%~dp0"

rem Single-root mode: LifePlanner keeps its writable state inside this folder.
set "LIFEPLANNER_PORTABLE=1"
set "LIFEPLANNER_DATA_DIR=%CD%\data"
set "PIP_CACHE_DIR=%CD%\data\cache\pip"
set "PYTHONPYCACHEPREFIX=%CD%\data\cache\pycache"
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"
if not exist "%PYTHONPYCACHEPREFIX%" mkdir "%PYTHONPYCACHEPREFIX%"

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv || python -m venv .venv || exit /b 1
  .venv\Scripts\python.exe -m pip install --upgrade pip || exit /b 1
  .venv\Scripts\python.exe -m pip install -r requirements.txt || exit /b 1
)
.venv\Scripts\python.exe main.py
endlocal

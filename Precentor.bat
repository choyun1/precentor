@echo off
rem Double-click to open Precentor. Close this window, or press Ctrl+C, to stop.
rem It runs itself again with its input from nul, so that Ctrl+C doesn't ask "Terminate batch job (Y/N)?";
rem the window then stays open only if something went wrong, to show what.
if not "%~1"=="--run" (
  call "%~f0" --run <nul
  if errorlevel 1 pause
  exit /b
)
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
rem keeps the Python packages up to date (quick when nothing is missing)
%PY% -m pip install -q --disable-pip-version-check -r requirements.txt
for /d %%r in (parish\plugins\*) do if exist "%%r\requirements.txt" %PY% -m pip install -q --disable-pip-version-check -r "%%r\requirements.txt"
%PY% tools\serve.py

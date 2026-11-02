@echo off
rem Double-click to open Precentor. Close its window, or press Ctrl+C, to stop.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
rem keeps the Python packages up to date (quick when nothing is missing)
%PY% -m pip install -q --disable-pip-version-check -r requirements.txt
for /d %%r in (parish\plugins\*) do if exist "%%r\requirements.txt" %PY% -m pip install -q --disable-pip-version-check -r "%%r\requirements.txt"
rem Precentor runs in a window of its own, outside this batch file, so that Ctrl+C stops it without cmd
rem asking "Terminate batch job (Y/N)?"; that window stays open only if something went wrong, to show what.
start "Precentor" cmd /c "%PY% tools\serve.py || pause"

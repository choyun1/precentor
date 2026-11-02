@echo off
rem Double-click to open the chant browser and service planner. Close this window to stop.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
rem keeps the Python packages up to date (quick when nothing is missing)
%PY% -m pip install -q --disable-pip-version-check -r requirements.txt
for /d %%r in (parish\plugins\*) do if exist "%%r\requirements.txt" %PY% -m pip install -q --disable-pip-version-check -r "%%r\requirements.txt"
%PY% tools\serve.py
pause

@echo off
rem Menu finder bot launcher. Asks for the API key once and saves it to .env, then starts the server.
rem ASCII only on purpose: cmd parses batch files with the console code page.
cd /d "%~dp0"
set PYTHONUTF8=1

set PY=
where python >nul 2>nul && python -c "import sys" >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py -3
if not defined PY goto nopython

set HASKEY=
if defined AXROUTER_API_KEY set HASKEY=1
if exist .env findstr /b /r "AXROUTER_API_KEY=." .env >nul 2>nul && set HASKEY=1
if defined HASKEY goto start

set /p KEY=Enter AXROUTER_API_KEY:
if not defined KEY goto nokey
>.env echo AXROUTER_API_KEY=%KEY%
echo Saved to .env. It is not uploaded to git.

:start
%PY% tools\server.py
pause
exit /b 0

:nopython
echo Python 3 is required. Install it from https://www.python.org/downloads/
pause
exit /b 1

:nokey
echo The key is empty.
pause
exit /b 1

@echo off
rem Starts the menu finder server automatically when you sign in to Windows (hidden, no window).
rem   autostart.bat          -> turn on  (also starts the server now)
rem   autostart.bat off      -> turn off
rem ASCII only on purpose: cmd parses batch files with the console code page.
cd /d "%~dp0"
set VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\menusearchbot.vbs

if /i "%~1"=="off" goto off

set PY=
where python >nul 2>nul && python -c "import sys" >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py -3
if not defined PY goto nopython
if not exist .env if not defined AXROUTER_API_KEY goto nokey

> "%VBS%" echo Set s = CreateObject("WScript.Shell")
>> "%VBS%" echo s.CurrentDirectory = "%~dp0"
>> "%VBS%" echo s.Run "cmd /c %PY% -X utf8 tools\server.py --background", 0, False
echo Autostart is ON. The server starts hidden every time you sign in.
echo Open the app: http://127.0.0.1:8765/  (or the installed app)
wscript "%VBS%"
exit /b 0

:off
if exist "%VBS%" del "%VBS%"
echo Autostart is OFF. A server that is already running keeps running until you sign out.
exit /b 0

:nopython
echo Python 3 is required. Install it from https://www.python.org/downloads/
pause
exit /b 1

:nokey
echo No .env file. Run run.bat once first to save the API key.
pause
exit /b 1

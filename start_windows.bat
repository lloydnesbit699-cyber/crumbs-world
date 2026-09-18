@echo off
rem Crumbs HUD launcher for Windows - double-click to run.
cd /d "%~dp0"

if not exist crumbs_hud.py (
  echo.
  echo  The zip wasn't fully extracted. Right-click crumbs-hud-v1.8.zip,
  echo  choose "Extract All", then double-click start_windows.bat inside
  echo  the extracted folder.
  echo.
  pause
  exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
  py crumbs_hud.py
  goto :end
)

where python >nul 2>nul
if not errorlevel 1 (
  python crumbs_hud.py
  goto :end
)

echo.
echo  Python 3 was not found on this computer.
echo  Install it free from https://www.python.org/downloads/
echo  ^(tick "Add python.exe to PATH" during install^), then double-click
echo  start_windows.bat again.
echo.
echo  Opening the download page now...
start https://www.python.org/downloads/

:end
pause

@echo off
setlocal
rem Safe default: install/connect only. SSH and Funnel require explicit flags.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tailscale-autobot.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Tailscale setup did not complete. Check the message above.
pause
exit /b %RESULT%

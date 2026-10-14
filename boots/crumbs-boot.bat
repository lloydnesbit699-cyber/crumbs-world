@echo off
setlocal
rem Double-click launcher. The PowerShell script locates the project relative
rem to itself, so the folder can live anywhere.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0crumbs-boot.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Crumbs World did not start. Check the message and logs above.
pause
exit /b %RESULT%

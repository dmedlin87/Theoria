@echo off
REM TheoEngine Quick Launcher (Windows Batch)
REM This is a simple wrapper that calls the PowerShell script

setlocal

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"

REM Default to 'full' mode if no argument provided
set "MODE=%~1"
if "%MODE%"=="" set "MODE=full"

REM Call PowerShell script
echo Starting TheoEngine in %MODE% mode...
echo.

powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\run.ps1" -Mode %MODE%

endlocal

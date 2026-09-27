@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-windows\Scripts\python.exe" goto missing
".venv-windows\Scripts\python.exe" -m dsan_display.windows %*
if errorlevel 1 pause
exit /b
:missing
echo Run Setup Windows.cmd first.
pause
exit /b 1

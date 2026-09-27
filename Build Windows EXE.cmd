@echo off
setlocal
cd /d "%~dp0"
py -3.13 -c "import platform,sys; assert sys.maxsize > 2**32 and platform.machine().lower() in ('amd64','x86_64'), 'Use Python 3.13 x64'"
if errorlevel 1 goto failed
if not exist ".venv-build-windows\Scripts\python.exe" py -3.13 -m venv .venv-build-windows
if errorlevel 1 goto failed
".venv-build-windows\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements-build-windows.txt
if errorlevel 1 goto failed
".venv-build-windows\Scripts\python.exe" tools\build_windows.py
if errorlevel 1 goto failed
echo Build complete: dist\DSANDisplay-windows-x64.zip
pause
exit /b 0
:failed
echo Build failed. Keep the error text above for diagnosis.
pause
exit /b 1

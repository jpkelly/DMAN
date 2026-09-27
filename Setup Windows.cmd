@echo off
setlocal
cd /d "%~dp0"
echo Setting up DSAN for Python 3.13 on Windows.
py -3.13 -c "import sys; assert sys.maxsize > 2**32, 'Install 64-bit Python 3.13'"
if errorlevel 1 goto failed
if not exist ".venv-windows\Scripts\python.exe" py -3.13 -m venv .venv-windows
if errorlevel 1 goto failed
".venv-windows\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Run Start DSAN.cmd next.
pause
exit /b 0
:failed
echo Setup failed. Install 64-bit Python 3.13 with the py launcher, then retry.
echo Keep the error text above if Python is installed but dependencies failed.
pause
exit /b 1

@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
  echo Run run.bat once to create the backend virtual environment first.
  exit /b 1
)
call "backend\.venv\Scripts\activate.bat"
python -m pip install -r ai\requirements.txt
if errorlevel 1 (
  echo YOLO dependency installation failed. Check Python compatibility and network, then retry.
  exit /b 1
)
echo Optional YOLO dependencies installed. The checkpoint downloads on first inference if network access permits.
echo No real video inference has been validated by this script.
pause

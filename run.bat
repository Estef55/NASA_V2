@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" py -m venv "backend\.venv"
call "backend\.venv\Scripts\activate.bat"
pip install -r "backend\requirements.txt" || exit /b 1
where npm >nul 2>nul || (echo Node.js/npm is required. Install Node.js 20+ and retry.& exit /b 1)
if not exist "frontend\node_modules" (
  pushd frontend
  call npm install
  if errorlevel 1 exit /b 1
  popd
)
start "LATIRA API" /D "%~dp0backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8000"
cd /d "%~dp0frontend"
npm run dev

@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "SKIP_DEPS_FLAG="
:parse_args
if "%~1"=="" goto after_args
if /I "%~1"=="--skip-deps" (
  set "SKIP_DEPS_FLAG=--skip-deps"
  shift
  goto parse_args
)
if /I "%~1"=="--help" goto show_help
if /I "%~1"=="-h" goto show_help
echo [ERROR] Opcion desconocida: %~1 ^(usa --skip-deps o --help^)
exit /b 1

:show_help
echo Uso: install_yolo.bat [--skip-deps]
echo   --skip-deps  Omite pip install de PyTorch/Ultralytics y solo descarga/verifica pesos YOLO.
exit /b 0

:after_args
if "%LATIRA_SKIP_YOLO_SETUP%"=="1" (
  echo [INFO] LATIRA_SKIP_YOLO_SETUP=1 esta activo: preparacion de YOLO Pose deshabilitada.
  echo [INFO] Desactiva LATIRA_SKIP_YOLO_SETUP para instalar YOLO Pose.
  exit /b 1
)

set "PY_CMD="
set "PY_EXE_BIN="
call :try_python "py -3"
if "%PY_CMD%"=="" call :try_python "python"
if "%PY_CMD%"=="" call :try_python "python3"
if "%PY_CMD%"=="" (
  echo [ERROR] Python 3.10 o superior ejecutable es obligatorio ^(se probaron: py -3, python, python3^).
  echo [INFO] Si Windows abrio el alias de Microsoft Store, desactiva el alias de Python en Configuracion o instala Python 3.11+ desde python.org.
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [INFO] Creating virtual environment in backend\.venv with %PY_CMD%...
  "%PY_EXE_BIN%" -m venv "backend\.venv"
  if errorlevel 1 (
    echo [ERROR] Failed to create backend\.venv.
    exit /b 1
  )
)

echo [INFO] Ensuring base backend dependencies...
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 (
  echo [ERROR] Failed to install backend\requirements.txt.
  exit /b 1
)

echo [INFO] Installing CPU PyTorch, Ultralytics, OpenCV Headless, and verifying yolo11n-pose.pt...
"backend\.venv\Scripts\python.exe" "ai\setup_yolo.py" --install %SKIP_DEPS_FLAG%
if errorlevel 1 (
  echo [ERROR] YOLO Pose installation or real inference verification failed.
  echo [INFO] Core LATIRA 2.0 can still run in lightweight mode via: run.bat --light
  exit /b 1
)

echo [OK] YOLO Pose installed, weights verified, and real inference passed.
exit /b 0

:try_python
set "CAND=%~1"
set "PY_EXE="
for /f "usebackq delims=" %%I in (`%CAND% -c "import os, sys; p = sys.executable; print(p) if (sys.version_info >= (3, 10) and os.path.isfile(p) and os.path.getsize(p) > 0) else sys.exit(1)" 2^>nul`) do set "PY_EXE=%%I"
if not "%PY_EXE%"=="" if exist "%PY_EXE%" (
  for %%A in ("%PY_EXE%") do if %%~zA GTR 0 (
    set "PY_CMD=%CAND%"
    set "PY_EXE_BIN=%PY_EXE%"
  )
)
exit /b 0

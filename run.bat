@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "MODE="
set "CLI_MODE_SET=0"
:parse_args
if "%~1"=="" goto after_args
if /I "%~1"=="--full" (
  set "MODE=full"
  set "CLI_MODE_SET=1"
  shift
  goto parse_args
)
if /I "%~1"=="--completo" (
  set "MODE=full"
  set "CLI_MODE_SET=1"
  shift
  goto parse_args
)
if /I "%~1"=="--light" (
  set "MODE=light"
  set "CLI_MODE_SET=1"
  shift
  goto parse_args
)
if /I "%~1"=="--ligero" (
  set "MODE=light"
  set "CLI_MODE_SET=1"
  shift
  goto parse_args
)
if /I "%~1"=="--help" goto show_help
if /I "%~1"=="-h" goto show_help
echo [ERROR] Opcion desconocida: %~1 ^(usa --full o --light^)
exit /b 1

:show_help
echo Uso: run.bat [--full ^| --light]
echo   --full   Instala dependencias generales y YOLO Pose ^(PyTorch CPU, Ultralytics, OpenCV Headless, pesos y prueba real^).
echo   --light  Instala solo el nucleo general sin descargar PyTorch ni pesos YOLO.
echo Tambien admite LATIRA_MODE=full^|light o LATIRA_SKIP_YOLO_SETUP=1 ^(equivale a --light^).
exit /b 0

:after_args
if "%CLI_MODE_SET%"=="0" if "%LATIRA_SKIP_YOLO_SETUP%"=="1" set "MODE=light"
if "%MODE%"=="" if not "%LATIRA_MODE%"=="" (
  if /I "%LATIRA_MODE%"=="full" set "MODE=full"
  if /I "%LATIRA_MODE%"=="completo" set "MODE=full"
  if /I "%LATIRA_MODE%"=="light" set "MODE=light"
  if /I "%LATIRA_MODE%"=="ligero" set "MODE=light"
  if /I "%LATIRA_MODE%"=="lightweight" set "MODE=light"
)
if "%MODE%"=="" if not "%LATIRA_MODE%"=="" (
  echo [ERROR] Valor invalido en LATIRA_MODE: %LATIRA_MODE% ^(usa full o light^)
  exit /b 1
)

if "%MODE%"=="" (
  echo Selecciona el modo de inicio de LATIRA 2.0:
  echo   1^) Modo completo ^(incluye instalacion y verificacion real de YOLO Pose^)
  echo   2^) Modo ligero ^(solo nucleo de LATIRA, sin PyTorch ni pesos YOLO^)
  set "CHOICE="
  set /p "CHOICE=Opcion [1/2] (predeterminado 1): "
)
if "%MODE%"=="" (
  if "%CHOICE%"=="2" (
    set "MODE=light"
  ) else if /I "%CHOICE%"=="light" (
    set "MODE=light"
  ) else if /I "%CHOICE%"=="ligero" (
    set "MODE=light"
  ) else (
    set "MODE=full"
  )
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

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js 20+ y npm son obligatorios.
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js 20+ y npm son obligatorios.
  exit /b 1
)
call npm --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm no es ejecutable en este entorno.
  exit /b 1
)

if not exist "data\database" mkdir "data\database"
if not exist "data\pose" mkdir "data\pose"
if not exist "data\uploads\thermography" mkdir "data\uploads\thermography"
if not exist "models" mkdir "models"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [INFO] Creando entorno virtual backend\.venv con %PY_CMD%...
  "%PY_EXE_BIN%" -m venv "backend\.venv"
  if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual backend\.venv.
    exit /b 1
  )
)

echo [INFO] Instalando dependencias generales del backend...
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 (
  echo [ERROR] Fallo la instalacion de backend\requirements.txt.
  exit /b 1
)

set "NEED_NPM_CI=0"
if not exist "frontend\node_modules" set "NEED_NPM_CI=1"
if "%LATIRA_FORCE_NPM_CI%"=="1" set "NEED_NPM_CI=1"
if "%NEED_NPM_CI%"=="1" (
  echo [INFO] Instalando dependencias reproducibles del frontend ^(npm ci^)...
  pushd frontend
  call npm ci --no-audit --no-fund
  if errorlevel 1 (
    popd
    echo [ERROR] Fallo npm ci en frontend.
    exit /b 1
  )
  popd
)

if /I "%MODE%"=="full" goto mode_full
goto mode_light

:mode_full
set "LATIRA_MODE=full"
set "LATIRA_SKIP_YOLO_SETUP=0"
"backend\.venv\Scripts\python.exe" "ai\setup_yolo.py" --enable >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se pudo registrar la configuracion de modo completo.
  exit /b 1
)
echo [INFO] Modo completo: verificando YOLO Pose...
"backend\.venv\Scripts\python.exe" "ai\setup_yolo.py" --verify >nul 2>nul
if not errorlevel 1 goto full_ready

echo [INFO] YOLO Pose aun no esta listo; iniciando instalacion y prueba de inferencia...
"backend\.venv\Scripts\python.exe" "ai\setup_yolo.py" --install
if not errorlevel 1 goto full_ready

echo.
echo [ERROR] La preparacion de YOLO Pose fallo. La instalacion completa NO se realizo.
if "%LATIRA_ALLOW_LIGHT_FALLBACK%"=="1" (
  echo [AVISO] Continuando en modo ligero por LATIRA_ALLOW_LIGHT_FALLBACK=1.
  set "MODE=light"
  goto mode_light
)
set "CONT="
set /p "CONT=Deseas continuar unicamente con el nucleo ligero ^(sin YOLO Pose^)? [s/N]: "
if /I "%CONT%"=="s" (
  set "MODE=light"
  goto mode_light
)
if /I "%CONT%"=="y" (
  set "MODE=light"
  goto mode_light
)
exit /b 1

:full_ready
echo [OK] Modo completo verificado: YOLO Pose operativo.
if "%YOLO_POSE_MODEL%"=="" if exist "%~dp0models\yolo11n-pose.pt" set "YOLO_POSE_MODEL=%~dp0models\yolo11n-pose.pt"
goto launch_app

:mode_light
set "LATIRA_MODE=light"
set "LATIRA_SKIP_YOLO_SETUP=1"
"backend\.venv\Scripts\python.exe" "ai\setup_yolo.py" --disable >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se pudo activar el modo ligero de YOLO Pose.
  exit /b 1
)
echo [INFO] Modo ligero activo: YOLO Pose deshabilitado ^(sin descargar ni cargar PyTorch/pesos^).
echo [INFO] Las rutas de inferencia /api/pose/* responderan con estado honesto 503/not_configured sin resultados ficticios.

:launch_app
if "%LATIRA_ENV%"=="" set "LATIRA_ENV=demo"
if "%LATIRA_DB_PATH%"=="" set "LATIRA_DB_PATH=%~dp0data\database\latira.sqlite3"
if "%POSE_STORAGE_DIR%"=="" set "POSE_STORAGE_DIR=%~dp0data\pose"
if "%POSE_HISTORY_DB%"=="" set "POSE_HISTORY_DB=%~dp0data\pose\history.sqlite3"
if "%LATIRA_THERMAL_DIR%"=="" set "LATIRA_THERMAL_DIR=%~dp0data\uploads\thermography"

start "LATIRA API" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
pushd "%~dp0frontend"
call npm run dev -- --host 127.0.0.1 --port 5173
set "FRONTEND_RC=%ERRORLEVEL%"
popd
if not "%FRONTEND_RC%"=="0" (
  echo [ERROR] El servidor frontend Vite termino con error.
  exit /b %FRONTEND_RC%
)
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

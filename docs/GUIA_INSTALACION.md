# Guía de Instalación Reproducible — LÁTIRA 2.0

Esta guía describe cómo instalar y ejecutar **LÁTIRA 2.0** desde cero en un equipo limpio en **Windows** o **Linux / macOS**, tanto en **Modo completo** (con YOLO Pose) como en **Modo ligero** (núcleo sin PyTorch ni pesos YOLO).

---

## 1. Requisitos previos

- **Python**: `3.10`, `3.11` (recomendado) o `3.12`.
  - En Debian/Ubuntu: `sudo apt update && sudo apt install -y python3-venv python3-pip`
  - En Windows: Python 3.11+ desde [python.org](https://www.python.org/downloads/) marcando *Add Python to PATH* (incluye lanzador `py -3`).
- **Node.js y npm**: Node.js `20+` y `npm` `10+`.
- **FFmpeg** *(recomendado solo si se usa subida/grabación de video en YOLO Pose)*: permite transcodificar el video anotado a H.264 `.mp4` reproducible en navegadores.
  - Linux: `sudo apt install -y ffmpeg`
  - Windows: `winget install Gyan.FFmpeg` (o agregar `ffmpeg.exe` al `PATH`).

---

## 2. Preparar directorios y variables de entorno

Extrae `LATIRA_2.0_FINAL.zip` de modo que exista una única raíz `LATIRA_2.0/` y sitúa tu terminal dentro de ella:

```bash
cd LATIRA_2.0
```

La aplicación **no autocarga archivos `.env`**. Usa `LATIRA_2.0/.env.example` como referencia y exporta las variables en tu sesión antes de iniciar:

### Linux / macOS
```bash
export LATIRA_ENV="demo"                        # Usa 'production' en servidores reales
export LATIRA_DB_PATH="$(pwd)/data/database/latira.sqlite3"
export LATIRA_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
# Opcional para LÁTI con Gemini:
# export GEMINI_API_KEY="TU_CLAVE"
# export LATIRA_LLM_MODEL="gemini-4-hydrogen"
```

### Windows (PowerShell)
```powershell
$env:LATIRA_ENV = "demo"
$env:LATIRA_DB_PATH = "$PWD\data\database\latira.sqlite3"
$env:LATIRA_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
# Opcional para LÁTI con Gemini:
# $env:GEMINI_API_KEY = "TU_CLAVE"
# $env:LATIRA_LLM_MODEL = "gemini-4-hydrogen"
```

---

## 3. Modos de instalación y arranque

Los scripts `run.sh` (Linux/macOS) y `run.bat` (Windows) implementan **dos modos explícitos**:

### Opción A — Modo completo (`--full`)
Instala dependencias generales del backend y del frontend, prepara `ai/setup_yolo.py` (PyTorch CPU, Ultralytics, OpenCV Headless sin conflictos, descarga y validación de `models/yolo11n-pose.pt`) y ejecuta una **prueba real de carga e inferencia**.

Si YOLO Pose falla (por red, espacio o plataforma), el script **no declara la instalación como completa**, informa claramente el error y pregunta si deseas continuar únicamente con el núcleo ligero.

```bash
# Linux / macOS
./run.sh --full
```
```powershell
# Windows (PowerShell o CMD)
.\run.bat --full
```

### Opción B — Modo ligero (`--light` o `LATIRA_SKIP_YOLO_SETUP=1`)
Instala **únicamente** las dependencias generales del backend (`backend/requirements.txt`) y del frontend (`npm ci` con `package-lock.json`), **sin descargar PyTorch ni pesos YOLO**. Las rutas `/api/pose/*` permanecen activas informando honestamente `not_configured` / `503` sin resultados ficticios.

```bash
# Linux / macOS
./run.sh --light
# Equivalente heredado:
LATIRA_SKIP_YOLO_SETUP=1 ./run.sh
```
```powershell
# Windows (PowerShell)
.\run.bat --light
# Equivalente heredado:
$env:LATIRA_SKIP_YOLO_SETUP = "1"; .\run.bat
```

*(Si ejecutas `./run.sh` o `.\run.bat` sin argumentos en una terminal interactiva, podrás elegir entre `1) Modo completo` y `2) Modo ligero`.)*

---

## 4. Instalación manual paso a paso (verificable)

### Linux / macOS
```bash
cd LATIRA_2.0
mkdir -p data/database data/pose data/uploads/thermography models
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt

# Frontend reproducible desde package-lock.json
cd frontend
npm ci
npm run build
cd ..

# Opcional: instalar y verificar YOLO Pose por separado
./install_yolo.sh
```

### Windows (PowerShell)
```powershell
cd LATIRA_2.0
New-Item -ItemType Directory -Force data\database, data\pose, data\uploads\thermography, models | Out-Null
py -3 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Frontend reproducible desde package-lock.json
Push-Location frontend
npm ci
npm run build
Pop-Location

# Opcional: instalar y verificar YOLO Pose por separado
.\install_yolo.bat
```

---

## 5. Puertos locales y comprobación inicial

- **Backend API**: `http://127.0.0.1:8000` (`/api/health` y `/docs`)
- **Frontend Vite**: `http://127.0.0.1:5173` (con proxy `/api` al puerto `8000`)

Comprobación rápida de salud del backend:
```bash
curl -s http://127.0.0.1:8000/api/health
```

---

## 6. Preparación de cuentas de demostración (`demo_tools.py`)

Si deseas pregenerar cuentas demo con contraseñas aleatorias seguras (24 caracteres) y sembrar días de escenario reproducible antes de abrir el navegador:

```powershell
# Windows PowerShell (desde LATIRA_2.0\)
$env:LATIRA_ENV = "demo"
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\python.exe -m app.demo_tools prepare --days 3
backend\.venv\Scripts\python.exe -m app.demo_tools show
```

Para limpiar solo el escenario demo (`demo=1`) conservando cuentas y datos reales (`demo=0`):
```powershell
backend\.venv\Scripts\python.exe -m app.demo_tools reset
```

---

## 7. Solución de problemas habituales en Windows

- **Alias de Microsoft Store para `python` / `python3`**: `run.bat` e `install_yolo.bat` excluyen automáticamente ejecutables vacíos (0 bytes) y prueban `py -3`, `python` y `python3`. Si falla, instala Python 3.11+ desde [python.org](https://www.python.org/downloads/) marcando *Add Python to PATH* o desactiva los alias en *Configuración -> Aplicaciones -> Alias de ejecución de aplicaciones*.
- **Error de `npm` o falta Node.js**: instala Node.js 20 LTS o superior y abre una nueva ventana de PowerShell para refrescar el `PATH`.
- **Rutas con espacios**: tanto `run.bat` como `install_yolo.bat` usan rutas relativas al proyecto (`%~dp0`) y entrecomillan rutas de Python y directorios.
- **Cambio entre modo completo y modo ligero**: puedes alternar ejecutando `.\run.bat --light` (persiste `light` en `data\pose_mode.json` sin borrar PyTorch ni los pesos) o `.\run.bat --full` (reactiva y verifica carga + inferencia real).
- **Render**: en el plan gratuito (`512 MiB` RAM), mantén `LATIRA_MODE=light` y `LATIRA_SKIP_YOLO_SETUP=1` como está configurado en `render.yaml`, ya que YOLO Pose completo requiere ~`635–724 MiB` Peak RSS.

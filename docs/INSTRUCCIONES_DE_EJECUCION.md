# Instrucciones de instalación y ejecución — LÁTIRA 2.0

**Plataforma de inteligencia para la salud y el bienestar de los astronautas.**  
*Prototipo académico y demostrativo. No es un dispositivo médico ni sustituye evaluación clínica profesional.*

---

## 1. Requisitos e dependencias previas

- **Python**: `3.10` o superior (`3.11` recomendado).
  - En Debian/Ubuntu asegúrate de contar con soporte de entornos virtuales: `sudo apt install python3-venv python3-pip`.
- **Node.js y npm**: Node.js `20+` y `npm` `10+`.
- **FFmpeg** *(recomendado para YOLO Pose)*: requerido para transcodificar el video anotado de salida a H.264 (`.mp4` con `yuv420p`), compatible directamente con navegadores Chromium, Edge y Firefox. Sin `ffmpeg`, Ultralytics guarda en formato `.mp4`/`.avi` nativo de OpenCV que algunos navegadores pueden no reproducir embebido.
- **Cámara web física** *(opcional para pruebas en vivo / grabación)* y conexión de red saliente hacia `osdr.nasa.gov`, `www.nasa.gov` y `www.asc-csa.gc.ca` *(opcional para verificación NASA/CSA en vivo)*.

---

## 2. Configuración del entorno

La aplicación no carga automáticamente archivos `.env`; define las variables en tu terminal antes de iniciar el backend (puedes tomar como referencia `LATIRA_2.0/.env.example`):

```bash
# Modo de ejecución: 'demo' habilita selector sin contraseña para demostración; 'production' exige clave
export LATIRA_ENV="production"
export LATIRA_DEMO_LOGIN="false"
export LATIRA_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"

# Base de datos SQLite local (fuera del repositorio en producción/pruebas)
export LATIRA_DB_PATH="./data/database/latira.sqlite3"

# Modelo generativo externo para LÁTI (solo en el servidor; nunca en el frontend)
# Opción Google AI Studio / Gemini:
export GEMINI_API_KEY=""
export LATIRA_LLM_MODEL="gemini-4-hydrogen"
export LATIRA_LLM_TIMEOUT_SECONDS="15"

# Configuración YOLO Pose
export YOLO_POSE_MODEL="./models/yolo11n-pose.pt"
export POSE_STORAGE_DIR="./data/pose"
export POSE_HISTORY_DB="./data/pose/history.sqlite3"
export POSE_MAX_UPLOAD_BYTES=104857600

# Almacenamiento de imágenes térmicas subidas o capturadas
export LATIRA_THERMAL_DIR="./data/uploads/thermography"
```

---

## 3. Instalación del backend, frontend y dependencias de YOLO Pose

Desde la raíz del proyecto descomprimido (`LATIRA_2.0/`):

### Linux / macOS
```bash
cd LATIRA_2.0
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt

# Frontend reproducible desde package-lock.json
cd frontend && npm ci && cd ..

# Opcional recomendado: preparar YOLO Pose, resolver OpenCV Headless y probar inferencia real
./install_yolo.sh
```

### Windows (PowerShell)
```powershell
cd LATIRA_2.0
py -3 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Frontend reproducible desde package-lock.json
Push-Location frontend; npm ci; Pop-Location

# Opcional recomendado: preparar YOLO Pose, resolver OpenCV Headless y probar inferencia real
.\install_yolo.bat
```

---

## 4. Configuración de los pesos de YOLO Pose (`yolo11n-pose.pt`)

El archivo binario `yolo11n-pose.pt` (~6.0 MB, licencia AGPL-3.0 de Ultralytics) **no se redistribuye dentro del ZIP** para mantener el paquete limpio y evitar binarios duplicados.

Opciones para disponer de los pesos en `models/yolo11n-pose.pt`:
1. **Instalador reproducible (recomendado)**: `./install_yolo.sh` o `.\install_yolo.bat` (invocan `ai/setup_yolo.py --install`) descargan atómicamente `yolo11n-pose.pt`, verifican tamaño e integridad ZIP, cargan el modelo y ejecutan una inferencia real sobre fotograma sintético.
2. **Ruta explícita local**: coloca el archivo `.pt` en `LATIRA_2.0/models/yolo11n-pose.pt` o apunta `YOLO_POSE_MODEL` a tu archivo local:
   ```bash
   export YOLO_POSE_MODEL="/ruta/absoluta/yolo11n-pose.pt"
   ```
3. **Modo ligero (`--light` o `LATIRA_SKIP_YOLO_SETUP=1`)**: la aplicación funciona normalmente en todas las demás áreas sin descargar PyTorch ni pesos, y el backend responde honestamente `503` / `not_configured` en `/api/pose/status`, `/api/pose/frame` y `/api/pose/process` sin inventar resultados.

---

## 5. Ejecución del backend y frontend

### Arranque rápido todo-en-uno
```bash
cd LATIRA_2.0
./run.sh --full    # Instala/verifica núcleo + YOLO Pose con prueba real
./run.sh --light   # Solo núcleo general (equivalente a LATIRA_SKIP_YOLO_SETUP=1 ./run.sh)
```
*(En Windows: `.\run.bat --full` o `.\run.bat --light`.)*

### Arranque manual en dos terminales

**Terminal 1 — Backend FastAPI (`http://127.0.0.1:8000`):**
```bash
cd LATIRA_2.0/backend
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- Salud del sistema: `http://127.0.0.1:8000/api/health`
- Documentación OpenAPI: `http://127.0.0.1:8000/docs`

**Terminal 2 — Frontend Vite + React (`http://127.0.0.1:5173`):**
```bash
cd LATIRA_2.0/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
*(El servidor de desarrollo de Vite reenvía automáticamente `/api/*` al puerto `8000`.)*

---

## 6. Requisitos de acceso a cámara en `localhost` vs HTTPS

Los navegadores modernos aplican restricciones estrictas sobre `navigator.mediaDevices.getUserMedia`:
- **En local (`http://localhost:5173` o `http://127.0.0.1:5173`)**: considerado *contexto seguro*; la cámara funciona tras conceder el permiso en el navegador.
- **En despliegue o red (`https://tu-dominio`)**: **es obligatorio usar HTTPS válido**. Si accedes mediante `http://192.168.x.x:5173` o HTTP sin TLS, el navegador bloqueará la cámara (`SecurityError` / `!window.isSecureContext`) y LÁTIRA mostrará un mensaje claro explicando la restricción.
- **Control exclusivo**: LÁTIRA nunca enciende ni graba la cámara en segundo plano. Si abres la cámara en *Movimiento (Pose)* y luego la abres en *Imagen térmica* (o cambias de vista / cierras sesión), la pista de video anterior se libera automáticamente (`track.stop()`).

---

## 7. Cómo probar paso a paso Pose en vivo, grabación y carga de video

1. **Inicia sesión** seleccionando el perfil **Astronauta** (o **Médico** / **Administrador**) en el selector de demostración con `LATIRA_ENV=demo` (o mediante usuario y contraseña si ejecutas en `LATIRA_ENV=production`).
2. Entra en **Movimiento (Pose)** en la barra lateral. Verifica el distintivo superior **Modelo YOLO Pose disponible** (o el aviso técnico si faltan pesos).
3. **Modo 1 — Cámara en vivo**:
   - Pulsa **Abrir cámara** y acepta el permiso del navegador. Si dispones de varias cámaras, utiliza el selector **Cambiar cámara**.
   - Confirma que ves la vista previa antes de iniciar.
   - Pulsa **Iniciar análisis en vivo**. Cada fotograma se envía secuencialmente a `POST /api/pose/frame` con el modelo YOLO Pose real y dibuja el esqueleto/puntos clave sobre el lienzo sin congelar la interfaz.
   - Mantén a una persona visible unos segundos y pulsa **Detener y finalizar análisis**.
   - Revisa el informe principal en español sencillo (*Resumen general*, *Observaciones interpretadas*, *Indicadores visuales*, *Limitaciones y advertencias*) y despliega *Detalles técnicos del análisis* si necesitas auditar datos numéricos o JSON.
4. **Modo 2 — Grabar desde cámara**:
   - Cambia a la pestaña **Grabar desde cámara** (abre la cámara si estaba cerrada).
   - Pulsa **Iniciar grabación**, observa el temporizador en pantalla y pulsa **Detener grabación**.
   - Revisa el clip grabado en el reproductor; pulsa **Repetir grabación** si deseas descartarlo o **Procesar video grabado** para enviarlo al modelo YOLO Pose (`POST /api/pose/process`).
5. **Modo 3 — Subir video existente**:
   - Cambia a **Subir video** (la cámara abierta se cerrará automáticamente).
   - Selecciona un archivo `.mp4`, `.mov`, `.avi`, `.mkv` o `.webm` (máx. 100 MiB). Revisa la vista previa local y pulsa **Analizar video con YOLO Pose**.
   - Si deseas interrumpir la carga, pulsa **Cancelar**. Al finalizar, revisa el video anotado, los fotogramas representativos, la gráfica de evolución postural y el informe en español sencillo.

---

## 8. Ejecución de pruebas automatizadas

### Linux / macOS (desde `LATIRA_2.0/`)
```bash
backend/.venv/bin/python -m compileall -q backend/app ai
PYTHONPATH=.:backend backend/.venv/bin/python -m unittest discover -s backend/tests -v
PYTHONPATH=.:backend backend/.venv/bin/python -m unittest discover -s ai/tests -v
npm --prefix frontend run build
```

### Windows PowerShell (desde `LATIRA_2.0/`)
```powershell
backend\.venv\Scripts\python -m compileall -q backend\app ai
$env:PYTHONPATH = ".;backend"
backend\.venv\Scripts\python -m unittest discover -s backend\tests -v
backend\.venv\Scripts\python -m unittest discover -s ai\tests -v
npm --prefix frontend run build
```

# Módulos de IA y adaptadores opcionales (`ai/`)

Todos los adaptadores están aislados dentro de `ai/`. Importar `ai` o ejecutar el núcleo de LÁTIRA 2.0 en **modo ligero** no requiere PyTorch, Ultralytics ni OpenCV.

---

## 1. YOLO Pose (`ai/setup_yolo.py`, `ai/yolo_video.py`, `ai/pose_interpreter.py`)

El router autenticado `backend/app/routers/pose.py` ya integra este módulo mediante `/api/pose/status`, `/api/pose/frame`, `/api/pose/live/complete`, `/api/pose/process`, `/api/pose/history`, `/api/pose/history/{analysis_id}/video` y `DELETE /api/pose/history/{analysis_id}`.

**Aviso obligatorio:** las detecciones de YOLO Pose corresponden exclusivamente a puntos clave geométricos y ángulos visuales (inclinación de tronco, hombros y cadera); **no constituyen mediciones fisiológicas ni diagnósticos médicos**.

### Modo ligero vs. Modo completo

La configuración efectiva sigue este orden de prioridad:
1. `LATIRA_SKIP_YOLO_SETUP=1` -> fuerza **modo ligero** (`lightweight`).
2. `LATIRA_YOLO_ENABLED=false` -> fuerza **modo ligero**.
3. `LATIRA_MODE=light|full` -> fuerza **modo ligero** o **modo completo**.
4. Archivo persistido `data/pose_mode.json` (gestionado por `ai/setup_yolo.py --disable` / `--enable` y por `run.sh` / `run.bat`).

- **Modo ligero (`not_configured` / `lightweight`)**:
  - No requiere `torch`, `torchvision`, `ultralytics`, `opencv-python-headless` ni `models/yolo11n-pose.pt`.
  - Si existen paquetes o pesos previos en disco, se conservan intactos pero **no se cargan ni se ejecuta inferencia**.
  - `/api/pose/status` informa `status: "not_configured"`, `mode: "lightweight"`, `yolo_enabled: false`.
  - `/api/pose/frame`, `/api/pose/live/complete` y `/api/pose/process` responden HTTP `503` sin fabricar resultados.
- **Modo completo (`available` / `full`)**:
  - Requiere Python `3.10+`, PyTorch CPU (`torch>=2.2,<3`, `torchvision>=0.17,<1` desde `https://download.pytorch.org/whl/cpu`), `ai/requirements.txt` (`ultralytics>=8.3,<9`, `opencv-python-headless>=4.10,<5`) y pesos válidos en `models/yolo11n-pose.pt` (ZIP PyTorch válido >= `1,000,000` bytes).
  - Resuelve automáticamente conflictos entre `opencv-python` / `opencv-contrib-python` y `opencv-python-headless`.
  - Verifica carga real del modelo (`YOLO(weights_path)`) e inferencia real sobre fotograma sintético `320×320` antes de informar `status: "available"`, `model_loadable: true`, `inference_ready: true`.
  - Consumo típico medido de memoria: ~`635–724 MiB` Peak RSS (por lo que despliegues de `512 MiB` como Render Free deben mantenerse en modo ligero).

### Comandos útiles de `ai/setup_yolo.py`

```bash
# Instalar dependencias CPU + Ultralytics + OpenCV Headless, descargar pesos y verificar inferencia real
backend/.venv/bin/python ai/setup_yolo.py --install

# Solo descargar/verificar pesos si las dependencias ya están instaladas
backend/.venv/bin/python ai/setup_yolo.py --install --skip-deps

# Consultar estado actual sin modificar paquetes ni descargar pesos
backend/.venv/bin/python ai/setup_yolo.py --check --json

# Verificar carga real e inferencia (código de salida 0 solo si status == "available")
backend/.venv/bin/python ai/setup_yolo.py --verify --json

# Cambiar modo persistido sin desinstalar paquetes
backend/.venv/bin/python ai/setup_yolo.py --disable   # pasa a modo ligero
backend/.venv/bin/python ai/setup_yolo.py --enable    # reactiva modo completo
```

*(En Windows PowerShell usa `backend\.venv\Scripts\python.exe ai\setup_yolo.py ...`.)*

---

## 2. Termografía (`ai/thermography.py`)

`ai.thermography.analyze_thermal_image(bytes, filename)` acepta imágenes térmicas/visuales proporcionadas por el usuario (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`) y devuelve únicamente metadatos de recepción (`core_temperature_inferred: false`). No decodifica paletas a temperaturas ni estima temperatura corporal central.

---

## 3. Fuentes científicas NASA y CSA (`ai/nasa_*.py`)

`ai/nasa_models.py`, `ai/nasa_catalog.py`, `ai/nasa_client.py` y `ai/nasa_sources.py` implementan el catálogo científico de las 5 fuentes oficiales NASA HRP / CSA (como referencias verificadas `reference_only`/`catalogued`, nunca como telemetría viva de sensores) más la consulta real a la API pública JSON de **NASA OSDR** (`osdr.nasa.gov`) bajo lista blanca estricta de dominios oficiales y separación total respecto a la línea base personal del astronauta.

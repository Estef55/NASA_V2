# Guía de Instalación y Verificación de YOLO Pose — LÁTIRA 2.0

El módulo de postura y movimiento (**YOLO Pose**) es **opcional**. LÁTIRA 2.0 puede operar en **modo ligero** (núcleo completo sin PyTorch ni pesos `.pt`) o en **modo completo** con inferencia geométrica real mediante `yolo11n-pose.pt`.

---

## 1. Política de distribución de `yolo11n-pose.pt`

- **¿Se incluye `yolo11n-pose.pt` dentro del ZIP?** **No.** El archivo binario (~6.0 MB, publicado por Ultralytics bajo licencia AGPL-3.0) se excluye intencionalmente del archivo ZIP para evitar redistribuir binarios de terceros, evitar duplicados y mantener el entregable liviano y verificable.
- **Ubicación única tras la instalación:** `LATIRA_2.0/models/yolo11n-pose.pt` (configurado por defecto en `.env.example` como `YOLO_POSE_MODEL=./models/yolo11n-pose.pt`).
- **Origen oficial:** `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt` (configurable con `LATIRA_YOLO_DOWNLOAD_URL` para espejos internos autorizados).

---

## 2. Qué hace el instalador `ai/setup_yolo.py`

Tanto `./install_yolo.sh` (Linux/macOS) como `.\install_yolo.bat` (Windows) y el modo `--full` de `run.sh`/`run.bat` invocan `ai/setup_yolo.py --install`, el cual ejecuta en orden:

1. **Verificación de Python `3.10+`** y creación/uso de `backend/.venv`.
2. **Instalación de PyTorch CPU compatible**: instala `torch>=2.2,<3` y `torchvision>=0.17,<1` desde `https://download.pytorch.org/whl/cpu` para evitar ruedas GPU incompatibles.
3. **Instalación de `ai/requirements.txt`**: `ultralytics>=8.3,<9` y `opencv-python-headless>=4.10,<5`.
4. **Resolución de conflictos OpenCV**: como `ultralytics` declara `opencv-python` como dependencia transitiva, `setup_yolo.py` desinstala `opencv-python` / `opencv-contrib-python` si coexistieran y reinstala `opencv-python-headless` para evitar colisiones GUI/headless en servidores sin X11.
5. **Descarga atómica e integridad de pesos**: descarga a un archivo temporal `.part`, valida que sea un archivo `.zip` válido de PyTorch (`zipfile.is_zipfile`) con tamaño superior a `1,000,000` bytes y solo entonces lo mueve a `models/yolo11n-pose.pt`. Si la red falla o se interrumpe, elimina `.part` sin dejar pesos corruptos.
6. **Prueba real de carga e inferencia**: instancia `YOLO(weights_path)` y ejecuta `detector.predict(...)` sobre una imagen sintética de `320×320` px. Solo si esta inferencia real tiene éxito se marca `inference_ready: true` y `mode: "full"`.

---

## 3. Comandos rápidos

### Instalación y verificación en Linux / macOS
```bash
cd LATIRA_2.0
./install_yolo.sh
```

### Instalación y verificación en Windows (PowerShell o CMD)
```powershell
cd LATIRA_2.0
.\install_yolo.bat
```

### Diagnóstico sin modificar el sistema
```bash
# Linux / macOS
backend/.venv/bin/python ai/setup_yolo.py --check --json

# Verificar con prueba real de carga e inferencia (código de salida != 0 si no está listo)
backend/.venv/bin/python ai/setup_yolo.py --verify --json
```

```powershell
# Windows PowerShell
backend\.venv\Scripts\python.exe ai\setup_yolo.py --check --json
backend\.venv\Scripts\python.exe ai\setup_yolo.py --verify --json
```

---

## 4. Estados informados en API e interfaz

La ruta autenticada `GET /api/pose/status` y `GET /api/integrations` informan:
- `status`: `"available"` (todo verificado), `"not_configured"` (modo ligero sin dependencias/pesos), `"unavailable"` (falta alguna librería) o `"error"` (pesos corruptos o fallo de carga/inferencia).
- `mode`: `"full"` o `"lightweight"`.
- Bandera por componente: `torch_installed`, `torchvision_installed`, `ultralytics_installed`, `opencv_installed`, `opencv_headless_installed`, `opencv_gui_installed`, `opencv_conflict`, `weights_present`, `weights_valid`, `model_loadable`, `inference_ready`.
- Nunca se exponen rutas internas absolutas del servidor ni se generan análisis ficticios cuando falta el modelo (las rutas `/api/pose/frame` y `/api/pose/process` devuelven HTTP `503`).

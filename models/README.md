# Modelos opcionales de YOLO Pose (`models/`)

El archivo de pesos `yolo11n-pose.pt` (~6.0 MB, licencia AGPL-3.0 de Ultralytics) **se excluye intencionalmente del paquete ZIP** para evitar redistribuir binarios de terceros duplicados y mantener el paquete liviano y verificable.

## Descarga y verificación reproducible

Ejecuta desde la raíz `LATIRA_2.0/`:

- **Linux / macOS**: `./install_yolo.sh` (o `./run.sh --full`)
- **Windows (PowerShell o CMD)**: `.\install_yolo.bat` (o `.\run.bat --full`)
- **Manual**: `backend/.venv/bin/python ai/setup_yolo.py --install`

El instalador `ai/setup_yolo.py`:
1. Instala PyTorch CPU compatible (`torch` y `torchvision`), `ultralytics` y `opencv-python-headless` (resolviendo conflictos con `opencv-python`).
2. Descarga `yolo11n-pose.pt` desde el lanzamiento oficial de Ultralytics (`https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt`) en `models/yolo11n-pose.pt`.
3. Verifica tamaño e integridad del archivo `.pt`, carga el modelo en memoria y ejecuta una inferencia real sobre un fotograma sintético antes de marcarlo como listo.

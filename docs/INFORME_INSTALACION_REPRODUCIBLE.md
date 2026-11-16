# Informe de Instalación Reproducible — LÁTIRA 2.0

Este documento resume las correcciones realizadas para garantizar una instalación limpia y reproducible de **LÁTIRA 2.0** desde cero en **Linux / macOS** y **Windows**.

---

## 1. Dependencias fijadas en el frontend (`frontend/package.json`)

Anteriormente `frontend/package.json` utilizaba `"latest"` en dependencias principales, rompiendo la reproducibilidad. Se fijaron las versiones reales verificadas en `package.json` y se regeneró `package-lock.json`:

| Paquete | Tipo | Rango fijado en `package.json` |
|---|---|---|
| `react` / `react-dom` | Runtime | `^19.3.1` |
| `lucide-react` | Runtime | `^1.72.0` |
| `recharts` | Runtime | `^3.10.1` |
| `@vitejs/plugin-react` | Runtime | `^6.3.0` |
| `vite` | Runtime | `^8.3.8` |
| `typescript` | Runtime / Build | `^7.0.2` |
| `@types/react` / `@types/react-dom` | Dev | `^19.3.0` |
| `tailwindcss` | Dev | `^3.4.17` |
| `postcss` | Dev | `^8.5.32` |
| `autoprefixer` | Dev | `^10.6.2` |

Comprobación ejecutada: `npm install`, eliminación de `node_modules/` y ejecución limpia de `npm ci && npm run build` (`140` paquetes instalados, compilación TypeScript + Vite exitosa).

---

## 2. Política del modelo YOLO Pose (`yolo11n-pose.pt`)

- **Decisión:** `models/yolo11n-pose.pt` (~6.0 MB, `6,255,593` bytes exactos tras descarga, licencia Ultralytics AGPL-3.0) **se excluye del ZIP** `LATIRA_2.0_RELEASE_CANDIDATA.zip`.
- **Justificación:** evita redistribuir pesos binarios de terceros bajo licencia AGPL-3.0, elimina copias duplicadas entre directorios y mantiene el paquete de entrega liviano y auditable (`models/README.md` documenta la procedencia oficial).
- **Descarga fiable e integridad (`ai/setup_yolo.py`):** descarga a `models/yolo11n-pose.pt.part`, verifica tamaño mínimo (`>= 1,000,000` bytes) y validez de archivo `.zip`/checkpoint PyTorch (`zipfile.is_zipfile`) antes de moverlo a `models/yolo11n-pose.pt`. Si falla la red, borra el `.part` sin dejar archivos corruptos.

---

## 3. Comportamiento de `run.sh`, `run.bat`, `install_yolo.sh` e `install_yolo.bat`

Se eliminó el comportamiento anterior en que la aplicación arrancaba silenciosamente tras un fallo de preparación de YOLO. Ahora existen dos modos explícitos:

1. **Modo completo (`--full` o opción 1 interactiva):**
   - Verifica Python `3.10+` y Node/npm.
   - Crea `backend/.venv`, instala `backend/requirements.txt` y prepara `frontend/node_modules` vía `npm ci`.
   - Ejecuta `ai/setup_yolo.py --verify`; si falta algún componente, ejecuta `ai/setup_yolo.py --install`:
     - Instala PyTorch CPU compatible (`torch>=2.2,<3`, `torchvision>=0.17,<1`) desde `https://download.pytorch.org/whl/cpu`.
     - Instala `ai/requirements.txt` (`ultralytics>=8.3,<9`, `opencv-python-headless>=4.10,<5`).
     - Detecta si `ultralytics` arrastró `opencv-python` (GUI) junto a `opencv-python-headless`, lo desinstala y fuerza `opencv-python-headless` limpio.
     - Descarga y valida `models/yolo11n-pose.pt`.
     - Carga `YOLO(...)` y ejecuta una inferencia real sobre una imagen sintética `320×320` px.
   - **Si falla:** imprime el error explícito, no declara la instalación completa y pregunta al usuario si desea abortar o continuar únicamente en **modo ligero**.
2. **Modo ligero (`--light` o `LATIRA_SKIP_YOLO_SETUP=1`):**
   - Instala únicamente las dependencias base del backend y frontend.
   - No descarga PyTorch, Ultralytics ni pesos `.pt`.
   - Informa claramente que YOLO Pose está deshabilitado (`mode: "lightweight"`) y que `/api/pose/*` devolverá `503` / `not_configured` sin fabricar resultados.

---

## 4. Comprobaciones reales ejecutadas en Linux (entorno limpio)

| Prueba | Resultado observado |
|---|---|
| `ai/setup_yolo.py --check --json` sin PyTorch ni pesos | `status: "not_configured"`, `mode: "lightweight"`, todos los flags en `false`, cero rutas internas expuestas. |
| `./install_yolo.sh` en copia limpia `/tmp/latira_yolo_test/LATIRA_2.0` | Instaló venv, FastAPI, Torch CPU, Ultralytics, desinstaló `opencv-python` en conflicto y dejó `opencv-python-headless`, descargó `yolo11n-pose.pt` (`6,255,593` bytes), cargó modelo e infirió correctamente (`status: "available"`, `mode: "full"`). |
| `POST /api/pose/frame` con JPEG real tras instalación | HTTP `200`, devolvió estructura completa de keypoints/geometría sin diagnóstico. |
| Descarga controlada fallida (`LATIRA_YOLO_DOWNLOAD_URL=http://127.0.0.1:9/bad.pt`) | `ok: False`, sin `yolo11n-pose.pt` ni `.pt.part` residual. |
| Consumo de memoria medido (`resource.getrusage`) en carga + inferencia YOLO | **`649,704 KB` (`~634.5 MiB`)** solo para el proceso Python de inferencia YOLO (base empírica directa de la restricción en Render 512 MiB). |

**Nota sobre Windows:** `run.bat` e `install_yolo.bat` implementan exactamente el mismo flujo con `py -3` / `python`, `backend\.venv\Scripts\python.exe`, `npm ci --no-audit --no-fund` y `ai\setup_yolo.py --install`. Se validaron sintácticamente y por paridad funcional; su ejecución directa en Windows queda sujeta a verificación en una máquina Windows real.

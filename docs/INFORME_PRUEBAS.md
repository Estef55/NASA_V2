# Informe de validación — LÁTIRA 2.0 (Cierre técnico)

## 1. Pruebas automatizadas ejecutadas

| Componente | Comando (desde `LATIRA_2.0/` o raíz) | Resultado real |
|---|---|---|
| **Backend API (`unittest`)** | `PYTHONPATH=.:backend backend/.venv/bin/python -m unittest discover -s backend/tests -v` | **37 tests OK** (50.492 s en orden estándar; también **37/37 OK** en 46.972 s ejecutando `test_pose_route` y `test_thermal_api` al inicio con `LATIRA_DB_PATH` centinela externo sin modificar y sin crear `data/`). |
| **Adaptadores IA / NASA / Pose (`unittest`)** | `PYTHONPATH=.:backend backend/.venv/bin/python -m unittest discover -s ai/tests -v` | **22 tests OK** (3.352 s: reglas locales LÁTI, cliente OSDR, intérprete geométrico Pose, validación de rutas Pose y termografía; `test_pose_router.py` standalone 5/5 OK en 3.266 s). |
| **Compilación Python** | `backend/.venv/bin/python -m compileall -q backend/app backend/tests ai` | **Exit code 0**. |
| **Build Frontend (`npm ci` + `npm run build`)** | `npm ci && npm run build` en `frontend/` (`tsc -b && vite build`) | **OK (2.88 s)**, 140 paquetes, 0 vulnerabilidades, sin chunks >500 kB (`vendor-charts` 414.65 kB, `vendor-react` 395.20 kB, `Modules` 80.82 kB, `index` 64.83 kB, `NasaScientificPanel` 24.75 kB, `vendor-icons` 12.17 kB, `Chart` 3.44 kB). |
| **Navegador E2E (Playwright Chromium)** | Recorrido completo `astro_demo`, `medic_demo`, `admin_demo`, `astro2`, reinicio de `uvicorn` y verificación en vivo de `osdr.nasa.gov` | **16/16 comprobaciones OK** (registros OSDR en vivo cargados, `0` errores JS en página, `0` errores inesperados de consola, sin desbordamiento horizontal en escritorio `1280×800` ni móvil `390×844`). |

## 2. Reproducibilidad y aislamiento de SQLite en pruebas

- `backend/tests/_db_isolation.py` configura un directorio temporal escribible y único por ejecución (`LATIRA_DB_PATH`, `POSE_STORAGE_DIR`, `POSE_HISTORY_DB`, `LATIRA_THERMAL_DIR`) **antes** de que cualquier módulo de prueba importe `app.database` o `app.main`, con limpieza automática al salir (`atexit`).
- Las 37 pruebas de backend y las 22 pruebas de IA/adaptadores no dependen del orden de descubrimiento de `unittest` ni utilizan o modifican `data/database/latira.sqlite3`.

## 3. Validaciones pendientes / fuera de alcance actual

- **Dependencias opcionales y hardware de YOLO Pose**: `ultralytics`, `opencv-python-headless` y `yolo11n-pose.pt` no vienen empaquetados en el entorno base ni en el ZIP limpio; no se ha probado inferencia YOLO con cámara real ni con pesos `.pt`. Ante su ausencia, `/api/pose/*` devuelve `503` / `not_configured` de forma honesta.
- **Hardware físico térmico y webcam**: no se probó webcam física (`getUserMedia`) ni conexión térmica física/SDK dedicado en este entorno headless; la interfaz mantiene el aviso de que una imagen convencional no estima temperatura central ni produce diagnóstico.
- **LLM externo**: LÁTI opera con reglas locales determinísticas (`origin: "rules_local"`); `lati_llm` se reporta como `not_configured`.
- **Scripts Windows**: `run.bat` e `install_yolo.bat` no se ejecutaron de forma nativa en Windows dentro de este contenedor Linux.
- **Validación clínica**: prototipo académico; no es un dispositivo médico.

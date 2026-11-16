# Informe de Estabilización Final — LÁTIRA 2.0

**Entregable:** `LATIRA_2.0_RELEASE_CANDIDATA.zip` (raíz única `LATIRA_2.0/`)
**Arquitectura preservada:** React 19 + TypeScript + Vite 8 + Tailwind CSS (`frontend/`) · FastAPI + Pydantic + SQLite (`backend/`) · IA / Pose / NASA / Termografía (`ai/`).
**Descargo de responsabilidad:** Prototipo académico demostrativo. No es un dispositivo médico ni sustituye evaluación clínica profesional.

---

## 1. Hallazgos críticos de la auditoría inicial (Bloque A)

Al comparar el archivo de partida (`látira-2.0-—-nasa-&-csa-scientific-integration.zip`) frente a los archivos históricos contenidos dentro de ese mismo paquete:

1. **Contaminación de empaquetado**: el ZIP original contenía una envoltura externa de Google AI Studio (`server.ts`, `src/`, `package.json`, `README.md`), dos ZIPs anidados (`LATIRA_2.0_FASE1_DEMO_LOGIN.zip` y `zip_4c66bc33.zip`), otro ZIP en `public/assets/aistudio/`, caché `frontend/tsconfig.app.tsbuildinfo` y copias inconsistentes.
2. **Regresión de archivos de Fase 1 dentro de Fase 2**: la carpeta `LATIRA_2.0/` del ZIP recibido conservaba los avances de Fase 2 (`lati_ai.py`, `routers_extra.py`, `main.py`, `WorkflowForms.tsx`, `App.tsx`, `PoseWorkspace.tsx`), pero varios archivos clave (`backend/app/routers/pose.py`, `ai/yolo_video.py`, `frontend/src/Modules.tsx`, `ai/nasa_*.py`, `backend/app/routers/nasa.py`, `backend/app/database.py`, `backend/app/services/health_baseline.py` y pruebas `_db_isolation`) habían retrocedido a una versión anterior, dejando desconectadas rutas que `PoseWorkspace.tsx` sí invocaba (`/api/pose/frame`, `/api/pose/live/complete`, `/api/pose/status`, `DELETE /api/pose/history/{id}`) y dejando de renderizar `<PoseWorkspace />` en `Modules.tsx`.
   - **Corrección aplicada:** se restauraron e integraron los módulos de Fase 1 íntegros sobre la base de Fase 2, conservando íntegramente `App.tsx`, `style.css`, `lati_ai.py`, `routers_extra.py`, `WorkflowForms.tsx` y `PoseWorkspace.tsx`.
3. **Dependencias frontend no fijadas**: `frontend/package.json` declaraba `"latest"` en todas sus dependencias, impidiendo `npm ci` reproducible. Se fijaron versiones compatibles reales y se regeneró `frontend/package-lock.json`.
4. **Falta de resolución automática de OpenCV Headless y de verificación real de inferencia**: `install_yolo.bat` / `run.sh` / `run.bat` no verificaban conflictos `opencv-python` vs `opencv-python-headless`, no ejecutaban prueba real de carga e inferencia antes de declarar listo YOLO, ni ofrecían modos explícitos completo vs ligero.
5. **CORS fijo a localhost y llamadas frontend relativas sin `VITE_API_BASE_URL`**: impedía separar frontend estático y backend API en Render u otros entornos sin proxy Vite.

---

## 2. Matriz de Auditoría por Componente

| Componente | Estado | Evidencia y observaciones verificadas |
|---|---|---|
| **Login con 3 tarjetas seleccionables (`Astronauta`, `Médico`, `Administrador`)** | **Implementado y comprobado** | Conservado diseño en tarjetas (`App.tsx`) respaldado por `GET /api/auth/demo-profiles` y `POST /api/auth/demo-login`. Deshabilitado en `LATIRA_ENV=production` (`403`). |
| **Autenticación, hashing y RBAC estricto** | **Implementado y comprobado** | `PBKDF2-SHA256` con sal aleatoria de 16 bytes (`security.py`), revocación al cambiar credenciales/rol/estado, aislamiento estricto de `admin` (`403` en rutas clínicas) y médicos limitados a asignados. Verificado en `test_security.py` y `test_stabilization_security.py`. |
| **Monitoreo real, línea base individual (`0.20`) y alertas explicables** | **Implementado y comprobado** | Separación `demo=0` vs `demo=1`, mínimo `3` muestras por indicador, umbral configurable `LATIRA_BASELINE_RELATIVE_DEVIATION=0.20`, alertas a partir de 4.º registro y seguimiento médico (`status='review'`). Verificado en `test_closure_audit.py` y `test_api_regressions.py`. |
| **LÁTI por voz (STT/TTS) + IA generativa externa + historial** | **Implementado y comprobado** | Adaptador server-side (`lati_ai.py`), aislamiento de métricas/alertas/chequeos en `rules_local`, deduplicación por `client_message_id`, estado honesto (`not_configured`, `configured`, `connected`, `connection_error`). Verificado en `test_lati_phase2.py` y `test_stabilization_security.py` (las llamadas externas en pruebas automatizadas usan callback HTTP controlado sin clave de producción). |
| **YOLO Pose (`setup_yolo.py`, `yolo_video.py`, `pose_interpreter.py`, `routers/pose.py`)** | **Implementado y comprobado** | Instalador `ai/setup_yolo.py` probado en limpio: PyTorch CPU + Ultralytics + resolución `opencv-python-headless` + descarga atómica `models/yolo11n-pose.pt` (`6,255,593` bytes) + carga real + inferencia `320×320` + `/api/pose/frame` HTTP `200`. En modo ligero devuelve `503` / `not_configured` honesto. |
| **Integración científica NASA / CSA / OSDR** | **Implementado y comprobado** | 5 fuentes oficiales catalogadas + consulta pública `osdr.nasa.gov` con lista blanca de dominios y separación estricta de línea base personal. Verificado en `test_nasa_integration.py` y `test_nasa_api.py`. |
| **Termografía (`ai/thermography.py`, `routers/thermography.py`)** | **Implementado y comprobado** | Validación de extensión, firma mágica y tamaño (`10 MiB`), aislamiento RBAC por astronauta/asignación y aviso explícito de que no estima temperatura corporal central. |
| **Interfaz bilingüe Español / Inglés** | **Implementado y comprobado** | Selector `ES / EN` en login y barra superior; cubre tarjetas demo, LÁTI, estados de integración y errores. |
| **Scripts reproducibles (`run.sh`, `run.bat`, `install_yolo.sh`, `install_yolo.bat`)** | **Implementado parcialmente** | `run.sh`, `install_yolo.sh` y `ai/setup_yolo.py` probados directamente en Linux. `run.bat` e `install_yolo.bat` revisados y alineados con la misma lógica para CMD/PowerShell, pero **no ejecutados nativamente en Windows** en este entorno Linux. |
| **Despliegue en Render (`render.yaml` + auditoría)** | **Pendiente (preparado y documentado)** | `render.yaml`, `LATIRA_CORS_ORIGINS`, `VITE_API_BASE_URL` y `docs/INFORME_AUDITORIA_RENDER.md` completados. **No se ejecutó un despliegue real en Render** por ausencia de credenciales/cuenta Render en este entorno. |
| **Voz en navegador real y conectividad en vivo con Gemini/OSDR** | **No verificable en entorno headless sin credenciales** | El comportamiento HTTP/UI y estados de error están verificados por pruebas unitarias y de integración; el acceso a micrófono físico Web Speech API en Chrome/Edge y llamadas con una `GEMINI_API_KEY` real requieren prueba manual en el entorno del operador. |

---

## 3. Seguridad y estado de integraciones

- **Producción segura por defecto**: el backend mantiene `LATIRA_ENV=production` y `LATIRA_DEMO_LOGIN=false` como valores predeterminados si no se define `LATIRA_ENV=demo` (reservado a `run.sh`/`run.bat` locales). En producción, `/api/auth/demo-login` responde `403`, `/api/auth/demo-profiles` devuelve `enabled: false`, y `ensure_demo_accounts` no siembra usuarios demo ni claves débiles en código.
- **Privacidad de rutas y secretos**: ninguna ruta (`/api/pose/status`, `/api/integrations`, `/api/lati/status`) expone rutas absolutas internas del servidor ni claves API.
- **Estados explícitos verificados en UI y API**:
  - `available` / `connected` / `partial_api_connected` / `configured` / `not_configured` / `unavailable` / `connection_error` (y `error` interno mapeado en UI).
  - YOLO distingue explícitamente `mode: "full"` vs `mode: "lightweight"` y muestra los 6 indicadores reales (`PyTorch`, `Ultralytics`, `OpenCV`, `Pesos`, `Carga`, `Inferencia`).
  - LÁTI distingue en el navegador *Voz disponible*, *Solo lectura por voz* y *Voz no disponible*, además del estado real del modelo en el servidor.

---

## 4. Resumen de pruebas ejecutadas

- `python -m compileall -q backend/app ai`: **OK** (sin errores de sintaxis).
- `backend/tests` (`unittest discover`): **54 pruebas OK** (`test_api_regressions.py`, `test_closure_audit.py`, `test_lati_phase2.py`, `test_nasa_api.py`, `test_new_backend_features.py`, `test_pose_route.py`, `test_security.py`, `test_stabilization_security.py`, `test_thermal_api.py`).
- `ai/tests` (`unittest discover`): **30 pruebas OK** (`test_adapters.py`, `test_nasa_integration.py`, `test_pose_interpreter.py`, `test_pose_router.py`, `test_setup_yolo.py`).
- `frontend`: `npm ci` + `npm run build` (`tsc -b && vite build`): **OK** (140 paquetes instalados limpiamente desde `package-lock.json`).
- **Instalación y prueba real de YOLO Pose desde cero** (`/tmp/latira_yolo_test/LATIRA_2.0`): `./install_yolo.sh` instaló `backend/.venv`, `torch`/`torchvision` CPU, `ultralytics`, resolvió conflicto `opencv-python` -> `opencv-python-headless`, descargó `models/yolo11n-pose.pt` (`6,255,593` bytes), verificó carga + inferencia real y respondió HTTP `200` en `POST /api/pose/frame`. Peak RSS medido del proceso de inferencia YOLO: `649,704 KB` (`~634.5 MiB`).

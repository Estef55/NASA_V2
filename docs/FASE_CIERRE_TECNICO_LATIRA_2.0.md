# FASE DE CIERRE TÉCNICO Y VALIDACIÓN FINAL — LÁTIRA 2.0

Fecha: 13 de noviembre de 2026  
Base auditada: `LATIRA_2.0_checkpoint_2026-11-13_f634ed51.zip` (47 archivos en `LATIRA_2.0/`, respaldo conservado durante la auditoría).

---

## Tabla de estado general

| Capacidad / Módulo | Estado | Evidencia / Observación |
|---|---|---|
| Autenticación, sesiones con TTL, hash PBKDF2-SHA256 con sal aleatoria y logout/revocación | **COMPLETADO Y VERIFICADO** | 4 pruebas de seguridad en `test_security.py` + flujo completo login/logout en navegador para 4 cuentas (`astro_demo`, `medic_demo`, `admin_demo`, `astro_two`, `role_test`). |
| Aislamiento RBAC estricto en backend y frontend (astronauta, médico asignado, administrador sin acceso clínico) | **COMPLETADO Y VERIFICADO** | Corregido en `main.py`, `routers_extra.py`, `thermography.py` y `App.tsx`; verificado con HTTP `403` para `admin` en todos los endpoints clínicos, `404` para `medic` en astronautas no asignados y aislamiento total entre astronautas en backend y Chromium. |
| Flujo Astronauta en navegador (panel, indicadores, evolución, demo 5 días, chequeo diario, registro real, alertas e historial) | **COMPLETADO Y VERIFICADO** | Probado en Playwright Chromium (42/42 comprobaciones aprobadas, 0 errores de consola). |
| Flujo Personal Médico en navegador (astronautas asignados, registros reales/demo, línea base por indicador, alertas, seguimientos, CSV, termografía) | **COMPLETADO Y VERIFICADO** | Probado en Playwright Chromium con `medic_demo` (`AST-001` asignado vs `AST-002` bloqueado con `404`), descarga de `astronaut-report.csv` y persistencia de seguimiento. |
| Flujo Administrador en navegador (gestión de usuarios, roles, contraseñas, activación, asignaciones e integraciones) | **COMPLETADO Y VERIFICADO** | Probado en Playwright Chromium reemplazando `window.prompt` por modales integrados y verificando creación, cambio de rol, cambio de contraseña y CRUD de asignaciones. |
| Inferencia real YOLO Pose (`ultralytics` + `yolo11n-pose.pt` + historial propietario + reproducción H.264) | **COMPLETADO Y VERIFICADO** | Corregida detección de `.avi` de Ultralytics y transcodificación H.264 con `ffmpeg` en `ai/yolo_video.py`; inferencia real validada sobre video MP4 de 5 cuadros (34 keypoints/cuadro, conf. media 0.5656) y reproducción en `<video>` en Chromium. |
| Optimización de frontend (code-splitting / lazy loading / separación de vendors) | **COMPLETADO Y VERIFICADO** | `App.tsx` carga diferida de `Chart` (Recharts) y `Modules`; `vite.config.ts` separa `vendor-charts`, `vendor-react`, `vendor-icons`. Build `vite` pasa sin errores ni advertencias >500 kB. |
| Asistente LÁTI local (`rules_local`) | **COMPLETADO Y VERIFICADO** | Persiste historial por astronauta, consulta indicadores reales (corregido formato `N/A`/`n/d` en registros parciales), explica alertas existentes y rechaza diagnósticos/prescripciones. |
| Termografía (carga segura, validación de firma, almacenamiento e historial por permisos) | **COMPLETADO Y VERIFICADO** | Validada carga PNG, rechazo de `admin` (`403`), acceso de astronauta propietario y médico asignado, y aviso explícito de no estimación de temperatura central. |
| Ejecución reproducible Linux/macOS (`run.sh`) y documentación `.env.example` | **COMPLETADO Y VERIFICADO** | `.env.example` actualizado con rutas de Pose/termografía; `run.sh` creado; paquete ZIP final verificado mediante extracción e instalación limpia. |
| Script de arranque Windows (`run.bat` y `install_yolo.bat`) | **IMPLEMENTADO, PERO NO VERIFICADO** | Revisados sintácticamente; no ejecutados en Windows nativo porque el entorno de validación es Linux. |
| Conexión con cámara térmica / SDK externo | **PENDIENTE** | No existe hardware ni credenciales configuradas; `/api/integrations` informa `not_connected`. |
| Proveedor LLM externo para LÁTI (`LATIRA_LLM_*`) | **PENDIENTE** | Variables definidas en `.env.example` sin conectar; fuera de alcance de esta fase. |
| Integración de fuentes científicas NASA (`ai/nasa_sources.py`) | **PENDIENTE** | Catálogo intencionalmente vacío (`[]`) y `/api/integrations` informa `not_connected`; reservado para la siguiente fase. |

---

## 1. Estado inicial del checkpoint

Al descomprimir y auditar `LATIRA_2.0_checkpoint_2026-11-13_f634ed51.zip`:
- **Backend (`backend/`)**: FastAPI + SQLite operativo, con 24 pruebas unitarias aprobadas y compilación Python sin errores. Sin embargo, el rol `admin` tenía acceso automático a datos clínicos en `/api/metrics`, `/api/alerts`, `/api/alerts/{id}/followups`, `/api/baseline`, `/api/admin/astronauts/{astronaut_id}`, `/api/admin/reports/astronauts.csv` y `/api/thermography/*`.
- **IA / YOLO Pose (`ai/`)**: 8 pruebas aprobadas con procesador sustituido (`mock`), sin dependencias `ultralytics`/`opencv-python-headless` instaladas ni inferencia real probada. Además, `ai/yolo_video.py` fallaba con salidas reales de Ultralytics en Linux porque Ultralytics genera `.avi` y el código solo buscaba `*.mp4` o el nombre de entrada exacto.
- **Frontend (`frontend/`)**: compilaba, pero generaba un único chunk JS monolítico (638.25 kB en el checkpoint; 894.62 kB al construir con Vite 8.3.8 del `package-lock.json` / `npm ci`) con advertencia >500 kB, importaba `recharts` y `Modules` de forma síncrona, usaba `window.prompt()` en administración, no enviaba `language` en `/api/checkins`, y mostraba pestañas clínicas al usuario `admin`.
- **Navegador**: solo se había comprobado la pantalla de login; faltaba el recorrido autenticado completo.

---

## 2. Archivos modificados y añadidos

Modificados dentro de `LATIRA_2.0/`:
- `backend/app/main.py`
- `backend/app/routers_extra.py`
- `backend/app/routers/pose.py`
- `backend/app/routers/thermography.py`
- `ai/yolo_video.py`
- `frontend/src/App.tsx`
- `frontend/src/Chart.tsx`
- `frontend/src/Modules.tsx`
- `frontend/vite.config.ts`
- `backend/tests/test_api_regressions.py`
- `ai/tests/test_adapters.py`
- `ai/tests/test_pose_router.py`
- `.env.example`
- `README.md`
- `docs/INFORME_PRUEBAS.md`

Añadido dentro de `LATIRA_2.0/`:
- `run.sh` (lanzador reproducible para Linux/macOS equivalente a `run.bat`).

Entregables generados en la raíz de trabajo:
- `FASE_CIERRE_TECNICO_LATIRA_2.0.md`
- `LATIRA_2.0_FINAL.zip`

---

## 3. Correcciones realizadas

1. **Aislamiento clínico del rol Administrador (Backend + Frontend)**:
   - `GET /api/metrics`, `GET /api/alerts`, `POST /api/alerts/{alert_id}/followups`, `GET /api/baseline`, `GET /api/admin/astronauts/{astronaut_id}`, `GET /api/admin/reports/astronauts.csv`, `GET /api/thermography/history` y `GET /api/thermography/image/{image_id}` ahora rechazan a `admin` con HTTP `403`.
   - En `App.tsx`, la sesión `admin` ya no consulta `/metrics` ni `/alerts`, oculta pestañas clínicas (`health`, `alerts`, `thermography`) y presenta un resumen administrativo sin datos clínicos (`RBAC ISOLATED`).
2. **Corrección real de `ai/yolo_video.py` y `backend/app/routers/pose.py`**:
   - `_find_saved_video` detecta salidas `.mp4`, `.avi`, `.mov`, `.mkv` o `.webm` producidas por Ultralytics.
   - `_finalize_video` transcodifica a H.264 `.mp4` (`libx264`, `yuv420p`, `+faststart`) cuando `ffmpeg` está disponible para reproducción nativa en `<video>` HTML5, o conserva la extensión real con su `media_type` correcto cuando no hay `ffmpeg`.
   - Limpieza automática de la subcarpeta temporal de Ultralytics (`shutil.rmtree`) y captura explícita de pesos faltantes para devolver HTTP `503` en `/api/pose/process`.
   - `/api/integrations` evalúa dinámicamente si `ultralytics` y el archivo `YOLO_POSE_MODEL` están presentes (`configured` vs `not_configured`).
3. **Correcciones de UX y estado en Frontend**:
   - `App.tsx` envía `language: lang` en `POST /api/checkins`.
   - `Modules.tsx` sustituye `window.prompt()` (cambio de contraseña y solicitud de `astronaut_id`) por modales integrados, sincroniza el listado padre mediante `onRefresh?.()`, reinicia formularios tras guardar y muestra metadatos completos en historial de Pose.
   - `vite.config.ts` usa `process.env.LATIRA_API_URL || 'http://127.0.0.1:8000'` para evitar conflictos IPv6 (`localhost` vs `127.0.0.1`).
4. **Corrección en LÁTI (`routers_extra.py`) y pruebas (`test_pose_router.py`)**:
   - `lati_chat` formatea valores faltantes en métricas parciales como `N/A` / `n/d` en lugar de `None bpm`.
   - `ai/tests/test_pose_router.py` parchea `app.routers.pose.process_video` para que la prueba de indisponibilidad funcione tanto con `ultralytics` instalado como sin él.

---

## 4. Recorrido autenticado de cada perfil (Playwright Chromium real)

Ejecutado contra backend Uvicorn + frontend Vite reales con base SQLite temporal:

- **Astronauta (`astro_demo` — `AST-001`)**:
  - Inicio de sesión y cierre de sesión verificados.
  - Panel `Overview`, tarjetas de indicadores, evolución en `Health data` (5 filas demo + gráfica Recharts SVG) y línea base personal (`SUFFICIENT` tras 3 muestras).
  - Escenario demo de 5 días (`Start scenario` + 4× `Next day`) generando alertas explicables en días 4 y 5.
  - Chequeo diario guardado con respuesta local de LÁTI.
  - Registro real de 3 mediciones manuales (`sleep`, `heart_rate`, `fatigue`, `mood`, `source`, `unit`).
  - Conversación con LÁTI leyendo registros reales e historial persistido.
  - Carga de video Pose real con reproducción H.264 en navegador y carga/previsualización de imagen térmica PNG.
  - Cambio de idioma EN ↔ ES y cierre de sesión con revocación de token.
- **Personal médico (`medic_demo`)**:
  - Inicio y cierre de sesión verificados.
  - Selector de `Assigned crew` muestra únicamente `AST-001` (excluye `AST-002` no asignado).
  - Consulta de registros reales (`3`) y demo (`5`), estado de línea base por indicador, alertas, seguimientos y descarga real de `astronaut-report.csv`.
  - Registro de seguimiento en alerta desde `Alerts & follow-up` (estado pasa a `In review`) y verificación en el perfil del astronauta.
  - Consulta de imagen térmica del astronauta asignado.
  - Verificación de bloqueo en backend: `GET /api/admin/astronauts/AST-002` y reporte CSV de `AST-002` devuelven HTTP `404`.
- **Administrador (`admin_demo`)**:
  - Inicio y cierre de sesión verificados.
  - Resumen administrativo aislado (`RBAC ISOLATED`) sin métricas, alertas ni termografías clínicas en UI.
  - Verificación directa en backend: `/api/metrics`, `/api/alerts`, `/api/baseline`, `/api/admin/astronauts/AST-001`, `/api/admin/reports/astronauts.csv` y `/api/thermography/history` devuelven HTTP `403`.
  - Creación de usuarios (`astro_two` con `AST-002`, `role_test` como `medic`), cambio de rol con modal (`medic` → `astronaut` `AST-003`), cambio de contraseña con modal y posterior inicio de sesión con la nueva clave, alta y retirada de asignación `medic_demo → AST-003`, y consulta de `/api/integrations`.
- **Segundo astronauta (`astro_two` — `AST-002`)**:
  - Confirmado que no ve métricas, alertas, historial de LÁTI, historial de Pose ni termografías de `AST-001`.
- **Consola y diseño**: 42/42 comprobaciones aprobadas, 0 errores de consola de UI, 0 errores JS no capturados y 0 desbordamientos horizontales en `1280×800` y `390×844`.

---

## 5. Validación YOLO Pose y evidencia de inferencia real

- **Dependencias instaladas y probadas**: `torch` (CPU), `torchvision`, `ultralytics==8.4.212`, `opencv-python-headless==5.0.0`, `ffmpeg`.
- **Pesos reales empleados**: `yolo11n-pose.pt` (6.0 MB, formato PyTorch `.pt`, descargado por Ultralytics desde el lanzamiento oficial `https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n-pose.pt`, licencia AGPL-3.0).
- **Video de prueba compatible**: MP4 H.264 `640×360` de 5 cuadros generado con `ffmpeg` a partir de la imagen de referencia oficial `ultralytics/assets/zidane.jpg`.
- **Resultados reales observados**:
  - Inferencia directa (`ai.yolo_video.process_video`): 5 cuadros procesados, **34 keypoints detectados por cuadro** (2 personas × 17 puntos COCO Pose), confianza media **0.5656**, salida transcodificada a H.264 `640×360` (`.mp4`), subcarpeta temporal eliminada.
  - Inferencia end-to-end vía navegador (`POST /api/pose/process` → `GET /api/pose/history` → `GET /api/pose/history/{id}/video`): video anotado reproducido correctamente dentro de `<video controls>` en Chromium con aviso explícito de que son detecciones geométricas y no mediciones médicas.
- **Limitaciones y distribución de pesos**: Por licencia AGPL-3.0 de Ultralytics, `yolo11n-pose.pt` no se empaqueta dentro de `LATIRA_2.0_FINAL.zip`. Para habilitarlo tras instalar `ai/requirements.txt`, basta definir `YOLO_POSE_MODEL=yolo11n-pose.pt` (descarga automática oficial en el primer uso con red) o señalar un archivo `.pt` local (`YOLO_POSE_MODEL=/ruta/yolo11n-pose.pt`). Sin pesos/dependencias, el backend responde honestamente HTTP `503`.

---

## 6. Optimización del frontend y tamaños obtenidos

- **Línea base sin optimizar (Vite 8.3.8)**: `dist/assets/index-B4p0oIP5.js` = **894.62 kB** (`gzip: 260.47 kB`) con advertencia de chunk >500 kB (el checkpoint original reportaba 638.25 kB en su entorno previo).
- **Estrategia aplicada** (sin alterar diseño ni ocultar advertencias; `chunkSizeWarningLimit` permanece en el valor por defecto `500`):
  - `React.lazy` + `Suspense` para `Modules.tsx` y `Chart.tsx` (`OverviewChart`, `HealthChart`).
  - `manualChunks` en `vite.config.ts` para separar `vendor-charts` (`recharts`/`d3-*`/`victory-vendor`), `vendor-react` (`react`/`react-dom`) y `vendor-icons` (`lucide-react`).
- **Tamaños finales (`npm run build`) — 0 errores y 0 advertencias**:
  - `dist/index.html`: **0.74 kB** (`gzip: 0.38 kB`)
  - `dist/assets/rolldown-runtime-XKyaHtl9.js`: **0.72 kB** (`gzip: 0.42 kB`)
  - `dist/assets/Chart-DwvjqaMk.js`: **2.87 kB** (`gzip: 0.81 kB`) *(diferido)*
  - `dist/assets/vendor-icons-DFaUPpyi.js`: **7.77 kB** (`gzip: 3.42 kB`)
  - `dist/assets/Modules-4pUCOmY9.js`: **35.57 kB** (`gzip: 7.87 kB`) *(diferido)*
  - `dist/assets/index-L--pd-8W.js`: **53.56 kB** (`gzip: 11.11 kB`) *(entrada principal)*
  - `dist/assets/vendor-react-CQJJAQ-s.js`: **395.20 kB** (`gzip: 120.65 kB`)
  - `dist/assets/vendor-charts-DkDSUY4U.js`: **414.65 kB** (`gzip: 120.86 kB`) *(diferido junto a `Chart`)*
  - `dist/assets/index-BB3Kryrn.css`: **20.24 kB** (`gzip: 5.94 kB`)
  - `dist/assets/Modules-DG51oc5I.css`: **1.87 kB** (`gzip: 0.73 kB`)

---

## 7. Estado real de LÁTI

- **Implementado con reglas locales (`origin: "rules_local"`)**:
  - Persistencia de conversación por `astronaut_id` en SQLite (`conversations`), accesible solo al rol `astronaut` autenticado (`GET /api/conversation`, `POST /api/lati/chat`, `POST /api/checkins`).
  - Consulta únicamente registros reales (`demo=0`) del astronauta autenticado: último registro guardado (`sleep`, `heart_rate`, `fatigue`, `mood`, formateando faltantes como `N/A`/`n/d`) y alertas abiertas existentes (`status != 'closed'`).
  - Explica alertas citando únicamente el motivo almacenado y añadiendo aviso no diagnóstico.
  - Ante preguntas fuera de reglas o solicitudes de diagnóstico/prescripción, declara explícitamente que no puede diagnosticar ni prescribir y remite al equipo médico.
- **No implementado / Pendiente**:
  - Conexión a proveedor LLM externo (`LATIRA_LLM_BASE_URL`, `LATIRA_LLM_API_KEY`, `LATIRA_LLM_MODEL` permanecen como placeholders sin cablear).
  - Comprensión semántica libre fuera de palabras clave (`alert/alerta/warning/aviso` y `sleep/sueño/heart/corazón/fatigue/fatiga/mood/ánimo`).

---

## 8. Resultados de todas las pruebas

| Suite / Verificación | Ejecutadas | Aprobadas | Fallidas | No ejecutadas | Detalle |
|---|---|---|---|---|---|
| Backend (`unittest discover -s tests`) | 26 | 26 | 0 | 0 | 24 originales + 2 nuevas (`test_admin_does_not_get_automatic_clinical_access`, `test_astronaut_cannot_access_other_astronaut_records`). |
| IA y adaptadores (`unittest discover -s ai/tests`) | 9 | 9 | 0 | 0 | 8 originales (con mock corregido en `test_pose_router.py`) + 1 nueva (`test_find_saved_video_detects_avi_output`). |
| Compilación Python (`compileall -q backend/app ai`) | 1 | 1 | 0 | 0 | Exit code 0. |
| Frontend (`npm run build`: `tsc -b && vite build`) | 1 | 1 | 0 | 0 | Exit code 0, sin advertencias. |
| Navegador E2E Playwright Chromium (3 roles + segundo astronauta + YOLO real) | 42 | 42 | 0 | 0 | Cubre autenticación, RBAC, demo, chequeo, métricas reales, LÁTI, YOLO Pose real H.264, termografía, CSV, modales admin e idioma EN/ES. |
| `run.bat` / `install_yolo.bat` en Windows nativo | 0 | 0 | 0 | 2 | No ejecutados por tratarse de entorno Linux; validado equivalente POSIX `run.sh`. |

---

## 9. Instalación y ejecución reproducible

- Backend: `backend/requirements.txt` instala exactamente las dependencias requeridas (`fastapi`, `uvicorn[standard]`, `pydantic`, `pytest`, `httpx`, `python-multipart`).
- Frontend: `frontend/package-lock.json` + `npm ci` / `npm install` reproducen las dependencias y compilan limpiamente.
- Variables de entorno: `.env.example` documenta todas las variables usadas (`LATIRA_DB_PATH`, `LATIRA_DEMO_PASSWORD`, `LATIRA_SESSION_TTL_SECONDS`, `LATIRA_BASELINE_RELATIVE_DEVIATION`, `YOLO_POSE_MODEL`, `POSE_STORAGE_DIR`, `POSE_HISTORY_DB`, `POSE_MAX_UPLOAD_BYTES`, `LATIRA_THERMAL_DIR`) sin ningún secreto.
- Base de datos: `init()` en `backend/app/main.py` y `ensure_table()` en `thermography.py` / `_connect()` en `pose.py` crean todas las tablas automáticamente al iniciar.
- Arranque automatizado: `run.bat` (Windows) y `run.sh` (Linux/macOS).

---

## 10. Limitaciones pendientes

1. **Integración NASA**: `ai/nasa_sources.py` devuelve `[]`; no hay fuentes externas conectadas ni verificadas.
2. **Termografía**: sin cámara ni SDK físico; solo recepción y almacenamiento seguro de imágenes sin inferencia térmica.
3. **LÁTI**: basado en reglas locales por palabras clave; sin LLM externo conectado.
4. **Pesos YOLO**: `yolo11n-pose.pt` no se redistribuye dentro del ZIP por licencia AGPL-3.0; requiere `ai/requirements.txt` y descarga oficial o ruta local en `YOLO_POSE_MODEL`.
5. **Modularización y pruebas Windows**: parte del esquema/rutas sigue en `backend/app/main.py` (funcional, no refactorizado para respetar arquitectura); `run.bat` no se ejecutó en Windows nativo.
6. **Alcance clínico**: prototipo académico; no validado como dispositivo médico ni sometido a pentest formal.

---

## 11. Contenido del ZIP final

`LATIRA_2.0_FINAL.zip` contiene la carpeta `LATIRA_2.0/` limpia y ejecutable:
- Código fuente completo (`backend/app/`, `backend/tests/`, `ai/`, `ai/tests/`, `frontend/src/`, `frontend/index.html`, configuraciones `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig*.json`, `tailwind.config.js`, `postcss.config.js`).
- Scripts de arranque y documentación (`run.bat`, `run.sh`, `install_yolo.bat`, `.env.example`, `.gitignore`, `README.md`, `docs/*`).
- **Excluidos**: `.venv`, `node_modules`, `frontend/dist`, `__pycache__`, `*.pyc`, `data/`, bases `.sqlite3`/`.db`, archivos `.env` con secretos y pesos `.pt` de terceros.

---

## 12. Instrucciones para ejecutar el proyecto

```bash
unzip LATIRA_2.0_FINAL.zip
cd LATIRA_2.0
export LATIRA_DEMO_PASSWORD="TuClaveLocalFuerte"   # En PowerShell: $env:LATIRA_DEMO_PASSWORD="TuClaveLocalFuerte"
./run.sh                                          # En Windows: .\run.bat
```
Abrir `http://127.0.0.1:5173` en el navegador (API en `http://127.0.0.1:8000`, documentación OpenAPI en `http://127.0.0.1:8000/docs`).  
Para habilitar YOLO Pose opcional: instalar `pip install -r ai/requirements.txt` dentro del entorno virtual del backend, definir `YOLO_POSE_MODEL=yolo11n-pose.pt` (o ruta local al `.pt`) y contar con `ffmpeg` en el `PATH` para salida H.264 reproducible en navegador.

---

## 13. Evaluación: ¿está listo para iniciar la fase de integración NASA?

**SÍ — con alcance delimitado.**  
La base técnica de LÁTIRA 2.0 queda estabilizada, verificada en navegador para los tres roles, con aislamiento RBAC real en backend/frontend (incluida la restricción clínica al rol administrador), frontend optimizado sin advertencias de bundle, LÁTI local verificado sin alucinaciones e inferencia real de YOLO Pose validada. La fase de integración NASA puede iniciarse de forma segura sobre `ai/nasa_sources.py` y `/api/integrations`, manteniendo el principio de no conectar ni afirmar fuentes externas sin metadatos, unidades y procedencia verificables.

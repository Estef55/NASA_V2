# LÁTIRA 2.0 — Plataforma de bienestar de astronautas

Prototipo académico integrado con frontend **React + TypeScript + Vite + Tailwind CSS** (`frontend/`), backend **FastAPI + Pydantic + SQLite** (`backend/`), módulos de IA y contexto científico (`ai/`) y documentación técnica (`docs/`).  
**No constituye un dispositivo médico ni sustituye evaluación clínica profesional.**

## Flujo central integrado

1. **Monitoreo personal (`POST /api/metrics`)**: el astronauta registra mediciones reales (`sleep`, `heart_rate`, `fatigue`, `mood`, `source`, `unit`, `recorded_at`, con `demo=0`), completamente separadas de los escenarios de demostración (`demo=1`).
2. **Línea base individual (`GET /api/baseline`)**: calcula la referencia aritmética por astronauta e indicador (requiere mínimo `3` muestras por indicador). Detecta automáticamente el modo activo según los registros más recientes y permite consulta explícita con `?demo=true|false`.
3. **Alertas explicables (`GET /api/alerts`)**: tanto los registros reales (`POST /api/metrics`, a partir del 4.º registro frente a la línea base previa del mismo astronauta) como los días 4–5 de la demo generan alertas explicables no diagnósticas cuando existe una desviación relativa configurable (`LATIRA_BASELINE_RELATIVE_DEVIATION`, predeterminado `0.20`). Cada alerta incluye los seguimientos médicos asociados.
4. **Chequeo diario guiado por LÁTI (`POST /api/checkins`, `GET /api/checkins`)**: registra el autorreporte diario de fatiga y ánimo, genera orientación no diagnóstica mediante reglas locales y guarda la traza en el historial de conversación del astronauta.
5. **LÁTI con interacción por voz e IA generativa (`POST /api/lati/chat`, `GET /api/lati/status`, `GET /api/conversation`)**:
   - **Texto y voz integrados en el chat**: admite entrada escrita (`input_mode: "text"`) y dictado por micrófono (`input_mode: "voice"` mediante Web Speech API) con indicación visual de escucha y respuesta hablada (`speechSynthesis`) con cancelación de solapamientos, botón de detención y filtrado de bloques técnicos/URLs. Todo el intercambio se conserva en el historial del astronauta.
   - **Aislamiento clínico y modelo generativo externo**: las consultas sobre métricas guardadas, línea base, chequeos y alertas abiertas se resuelven localmente con los registros reales del astronauta autenticado (`rules_local`, sin enviar telemetría privada al proveedor externo); las consultas científicas NASA/CSA usan el catálogo verificado; la conversación abierta utiliza el modelo generativo externo configurado en el servidor (`GEMINI_API_KEY` / `LATIRA_LLM_API_KEY` — Google AI Studio Gemini o endpoint compatible OpenAI) con continuidad de sesión y respaldo local controlado ante errores o ausencia de clave API. `/api/integrations` y `POST /api/integrations/lati/verify` informan el estado real sin simular conexiones.
6. **Seguimiento médico y RBAC (`POST /api/alerts/{id}/followups`, `/api/admin/*`)**: el personal médico solo accede a astronautas asignados, agrega notas de seguimiento que pasan la alerta a estado `review` (visibles también para el astronauta) y exporta reportes CSV por astronauta y modo (`demo=true|false`). La cuenta administrativa gestiona usuarios, roles, asignaciones e integraciones, revocando sesiones activas al modificar credenciales, roles o estado, sin acceso automático a telemetría clínica.

## Módulos complementarios

- **YOLO Pose (`ai/yolo_video.py`, `ai/pose_interpreter.py`, `backend/app/routers/pose.py`)**: soporta análisis en vivo por fotogramas (`/api/pose/frame` + `/api/pose/live/complete`), grabación y subida de video (`/api/pose/process`). Describe patrones geométricos de postura y movimiento (nunca diagnósticos clínicos). Si faltan dependencias opcionales (`ai/requirements.txt`) o los pesos `.pt`, informa `503` / `not_configured` sin inventar resultados.
- **Termografía (`ai/thermography.py`, `backend/app/routers/thermography.py`)**: valida formato/tamaño/firma de imagen (`.png`, `.jpg`, `.tif`), almacena de forma aislada por astronauta y asignaciones, e informa explícitamente que una imagen visual/superficial no estima temperatura corporal central ni produce diagnósticos.
- **Fuentes NASA y CSA (`ai/nasa_sources.py`, `ai/nasa_catalog.py`, `ai/nasa_client.py`, `backend/app/routers/nasa.py`)**: cataloga las 5 fuentes oficiales NASA HRP / CSA como referencias científicas verificadas y consulta en vivo la API pública NASA OSDR (`osdr.nasa.gov`) bajo lista blanca de dominios oficiales, separando estrictamente estos datos de la línea base personal.

## Modos de ejecución: Ligero vs. Completo

LÁTIRA 2.0 admite dos modos explícitos (persistidos en `data/pose_mode.json` o controlados mediante `LATIRA_MODE` / `LATIRA_SKIP_YOLO_SETUP`):

| Aspecto | Modo ligero (`--light`) | Modo completo (`--full`) |
|---|---|---|
| **Funcionalidades activas** | Todo el núcleo: autenticación/RBAC, monitoreo real, línea base, alertas, seguimientos, CSV, chequeo diario, LÁTI (voz + Gemini/reglas), termografía y NASA/CSA OSDR. | Todo lo del modo ligero **más** inferencia geométrica real de YOLO Pose en vivo (`/api/pose/frame`), grabación y video (`/api/pose/process`). |
| **Dependencias requeridas** | Python `3.10+`, `backend/requirements.txt`, Node.js `20+` y `frontend/package-lock.json`. | Lo anterior **más** PyTorch CPU (`torch`, `torchvision`), `ai/requirements.txt` (`ultralytics`, `opencv-python-headless`), pesos `models/yolo11n-pose.pt` (~6 MB) y opcionalmente `ffmpeg` para transcodificación `.mp4` H.264. |
| **Limitaciones / recursos** | No carga PyTorch ni pesos; `/api/pose/status` informa `not_configured` (`lightweight`) y los endpoints de procesamiento responden `503` sin resultados ficticios. | Consume ~`635–724 MiB` Peak RSS en inferencia CPU. **No apto para Render Free (`512 MiB`)**, por lo que `render.yaml` mantiene el modo ligero en producción gratuita. |

## Ejecución rápida (Windows y Linux / macOS)

Los scripts `run.bat` y `run.sh` activan `LATIRA_ENV=demo` por defecto para habilitar el selector de perfiles de demostración sin contraseña (`Astronauta`, `Médico`, `Administrador`) y admiten dos modos explícitos:

- **Modo completo (`--full`)**: instala dependencias generales, instala/verifica PyTorch CPU + Ultralytics + OpenCV Headless + `models/yolo11n-pose.pt` y ejecuta una prueba real de carga e inferencia (`320×320`). Si YOLO falla, informa claramente el error y pregunta si deseas continuar en modo ligero.
- **Modo ligero (`--light` o `LATIRA_SKIP_YOLO_SETUP=1`)**: instala únicamente el núcleo general sin descargar PyTorch ni pesos YOLO; las rutas `/api/pose/*` informan honestamente `503` / `not_configured`.

### Windows (PowerShell o CMD)
```powershell
cd LATIRA_2.0
.\run.bat --full    # o .\run.bat --light (núcleo sin YOLO)
.\install_yolo.bat  # opcional para preparar y verificar YOLO Pose por separado
```
*(Si PowerShell bloquea scripts o si estás en CMD, también puedes invocar `cmd /c run.bat --light`.)*

### Linux / macOS
```bash
cd LATIRA_2.0
./run.sh --full     # o ./run.sh --light (núcleo sin YOLO)
./install_yolo.sh   # opcional para preparar y verificar YOLO Pose por separado
```

## Preparación de cuentas de demostración (`backend/app/demo_tools.py`)

Para entornos locales de demostración (`LATIRA_ENV=demo`), `app.demo_tools` genera cuentas demo faltantes (`astro_demo`, `medic_demo`, `admin_demo`) con **contraseñas aleatorias de 24 caracteres** almacenadas únicamente en local (`data/database/.demo_credentials.json` con permisos `0600`), sin sobrescribir cuentas reales existentes y manteniendo el bloqueo total en `LATIRA_ENV=production`:

```bash
# Linux / macOS (desde LATIRA_2.0/)
LATIRA_ENV=demo PYTHONPATH=backend backend/.venv/bin/python -m app.demo_tools prepare --days 3
LATIRA_ENV=demo PYTHONPATH=backend backend/.venv/bin/python -m app.demo_tools show
LATIRA_ENV=demo PYTHONPATH=backend backend/.venv/bin/python -m app.demo_tools reset
```

```powershell
# Windows PowerShell (desde LATIRA_2.0/)
$env:LATIRA_ENV = "demo"; $env:PYTHONPATH = "backend"
backend\.venv\Scripts\python.exe -m app.demo_tools prepare --days 3
backend\.venv\Scripts\python.exe -m app.demo_tools show
backend\.venv\Scripts\python.exe -m app.demo_tools reset
```

Para detalles completos de instalación reproducible, política de `models/yolo11n-pose.pt`, variables (`LATIRA_CORS_ORIGINS`, `VITE_API_BASE_URL`), auditoría Render y pruebas automatizadas, consulta `docs/GUIA_INSTALACION.md`, `docs/GUIA_INSTALACION_YOLO_POSE.md`, `docs/INFORME_AUDITORIA_RENDER.md`, `docs/ESTADO_TECNICO.md` y `docs/INSTRUCCIONES_DE_EJECUCION.md`.

## Seguridad y buenas prácticas

- En producción (`LATIRA_ENV=production`, valor predeterminado del backend), el acceso sin contraseña permanece deshabilitado (`403`), `app.demo_tools` rechaza cualquier operación de demostración, y las cuentas demo solo se crean en una base vacía si `LATIRA_DEMO_PASSWORD` está definida en el entorno.
- En modo demostración (`LATIRA_ENV=demo`), la inicialización asegura únicamente las cuentas demo faltantes (`astro_demo`, `medic_demo`, `admin_demo`) y la asignación `medic_demo -> AST-001` sin borrar ni sobrescribir cuentas o métricas reales (`demo=0`).
- CORS se controla mediante `LATIRA_CORS_ORIGINS` (sin comodín `*` con credenciales); la URL del backend en despliegues separados del frontend se configura en compilación con `VITE_API_BASE_URL`.
- LÁTIRA no está conectada a sensores espaciales, telemetría privada de vuelo de NASA ni dispositivos médicos certificados; las fuentes NASA/CSA externas corresponden a catálogo científico de referencia y metadatos públicos de `osdr.nasa.gov`.
- La carpeta `data/`, las bases SQLite en ejecución y los pesos binarios `.pt` se excluyen del paquete de entrega limpia.

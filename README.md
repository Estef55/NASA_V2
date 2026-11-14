# LÁTIRA 2.0 — Plataforma de bienestar de astronautas

Prototipo académico integrado con frontend **React + TypeScript + Vite + Tailwind CSS** (`frontend/`), backend **FastAPI + Pydantic + SQLite** (`backend/`), módulos de IA y contexto científico (`ai/`) y documentación técnica (`docs/`).  
**No constituye un dispositivo médico ni sustituye evaluación clínica profesional.**

## Flujo central integrado

1. **Monitoreo personal (`POST /api/metrics`)**: el astronauta registra mediciones reales (`sleep`, `heart_rate`, `fatigue`, `mood`, `source`, `unit`, `recorded_at`, con `demo=0`), completamente separadas de los escenarios de demostración (`demo=1`).
2. **Línea base individual (`GET /api/baseline`)**: calcula la referencia aritmética por astronauta e indicador (requiere mínimo `3` muestras por indicador). Detecta automáticamente el modo activo según los registros más recientes y permite consulta explícita con `?demo=true|false`.
3. **Alertas explicables (`GET /api/alerts`)**: tanto los registros reales (`POST /api/metrics`, a partir del 4.º registro frente a la línea base previa del mismo astronauta) como los días 4–5 de la demo generan alertas explicables no diagnósticas cuando existe una desviación relativa configurable (`LATIRA_BASELINE_RELATIVE_DEVIATION`, predeterminado `0.20`). Cada alerta incluye los seguimientos médicos asociados.
4. **Chequeo diario guiado por LÁTI (`POST /api/checkins`, `GET /api/checkins`)**: registra el autorreporte diario de fatiga y ánimo, genera orientación no diagnóstica mediante reglas locales y guarda la traza en el historial de conversación del astronauta.
5. **LÁTI (`POST /api/lati/chat`, `GET /api/conversation`)**: responde únicamente con los registros reales del astronauta autenticado (últimas métricas, línea base, chequeos y alertas abiertas) y referencias científicas verificadas de NASA/CSA en español e inglés, con origen explícito `rules_local` y auditoría. Si se configuran `LATIRA_LLM_BASE_URL` y `LATIRA_LLM_API_KEY`, `/api/integrations` refleja el estado `configured` sin simular conexiones cuando están ausentes.
6. **Seguimiento médico y RBAC (`POST /api/alerts/{id}/followups`, `/api/admin/*`)**: el personal médico solo accede a astronautas asignados, agrega notas de seguimiento que pasan la alerta a estado `review` (visibles también para el astronauta) y exporta reportes CSV por astronauta y modo (`demo=true|false`). La cuenta administrativa gestiona usuarios, roles, asignaciones e integraciones, revocando sesiones activas al modificar credenciales, roles o estado, sin acceso automático a telemetría clínica.

## Módulos complementarios

- **YOLO Pose (`ai/yolo_video.py`, `ai/pose_interpreter.py`, `backend/app/routers/pose.py`)**: soporta análisis en vivo por fotogramas (`/api/pose/frame` + `/api/pose/live/complete`), grabación y subida de video (`/api/pose/process`). Describe patrones geométricos de postura y movimiento (nunca diagnósticos clínicos). Si faltan dependencias opcionales (`ai/requirements.txt`) o los pesos `.pt`, informa `503` / `not_configured` sin inventar resultados.
- **Termografía (`ai/thermography.py`, `backend/app/routers/thermography.py`)**: valida formato/tamaño/firma de imagen (`.png`, `.jpg`, `.tif`), almacena de forma aislada por astronauta y asignaciones, e informa explícitamente que una imagen visual/superficial no estima temperatura corporal central ni produce diagnósticos.
- **Fuentes NASA y CSA (`ai/nasa_sources.py`, `ai/nasa_catalog.py`, `ai/nasa_client.py`, `backend/app/routers/nasa.py`)**: cataloga las 5 fuentes oficiales NASA HRP / CSA como referencias científicas verificadas y consulta en vivo la API pública NASA OSDR (`osdr.nasa.gov`) bajo lista blanca de dominios oficiales, separando estrictamente estos datos de la línea base personal.

## Ejecución rápida (Windows y Linux / macOS)

### Windows
```powershell
cd LATIRA_2.0
$env:LATIRA_DEMO_PASSWORD = "TuClaveLocalFuerte"
.\run.bat
```

### Linux / macOS
```bash
cd LATIRA_2.0
export LATIRA_DEMO_PASSWORD="TuClaveLocalFuerte"
./run.sh
```

Para detalles completos de instalación manual, variables de entorno, pesos opcionales de YOLO Pose (`yolo11n-pose.pt`) y pruebas automatizadas, consulta `docs/INSTRUCCIONES_DE_EJECUCION.md`.

## Seguridad y buenas prácticas

- Las cuentas demo (`astro_demo`, `medic_demo`, `admin_demo`) solo se crean en una base SQLite vacía si `LATIRA_DEMO_PASSWORD` está definida en el entorno. Nunca guardes contraseñas reales en el código o repositorios.
- La carpeta `data/` y la base SQLite se generan únicamente en tiempo de ejecución y se excluyen de los paquetes de entrega limpia.

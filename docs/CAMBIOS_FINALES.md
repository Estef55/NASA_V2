# Registro de Cambios Finales — Estabilización de LÁTIRA 2.0

Este documento detalla los cambios ejecutados respecto al paquete de partida (`látira-2.0-—-nasa-&-csa-scientific-integration.zip`) para producir la entrega limpia `LATIRA_2.0_RELEASE_CANDIDATA.zip`.

---

## 1. Limpieza de empaquetado y estructura única

- Eliminada la envoltura externa de AI Studio, archivos ZIP anidados (`LATIRA_2.0_FASE1_DEMO_LOGIN.zip`, `zip_4c66bc33.zip`, `public/assets/aistudio/*.zip`), caché `frontend/tsconfig.app.tsbuildinfo`, `node_modules/`, `.venv/`, `dist/`, `__pycache__/` y bases SQLite en ejecución.
- Garantizada una única carpeta raíz `LATIRA_2.0/` dentro de `LATIRA_2.0_RELEASE_CANDIDATA.zip`.
- Excluido `models/yolo11n-pose.pt` del ZIP y documentada su descarga verificada en `models/README.md` y `docs/GUIA_INSTALACION_YOLO_POSE.md`.

---

## 2. Restauración de regresiones detectadas en el ZIP de origen

Sobre la base de Fase 2 del ZIP recibido se reintegraron los módulos completos de Fase 1 que habían quedado desactualizados en la copia exterior:
- `ai/yolo_video.py`, `backend/app/routers/pose.py`, `ai/tests/test_pose_router.py`: restaurado el soporte completo de análisis en vivo (`/api/pose/frame`, `/api/pose/live/complete`), estado detallado (`/api/pose/status`) y borrado de historial (`DELETE /api/pose/history/{id}`).
- `frontend/src/Modules.tsx`: restaurado el renderizado de `<PoseWorkspace />`.
- `ai/nasa_sources.py`, `ai/nasa_catalog.py`, `ai/nasa_client.py`, `ai/nasa_models.py`, `backend/app/routers/nasa.py`, `ai/tests/test_nasa_integration.py`, `frontend/src/NasaScientificPanel.tsx`, `frontend/src/Chart.tsx`: restaurada la versión íntegra verificada de NASA/CSA/OSDR y gráficas.
- `backend/app/database.py`, `backend/app/services/health_baseline.py`, `backend/app/routers/thermography.py` y suite `backend/tests/{_db_isolation.py,test_api_regressions.py,test_nasa_api.py,test_new_backend_features.py,test_pose_route.py,test_security.py,test_thermal_api.py}`: restaurados `timeout=30.0`, corrección `before_metric_id` y aislamiento de base de datos en pruebas.

---

## 3. Estabilización, instalación reproducible y seguridad

- **`ai/setup_yolo.py`** *(nuevo)*: instalador y verificador multiplataforma (`--install`, `--verify`, `--check`, `--skip-deps`, `--json`) para PyTorch CPU, Ultralytics, detección/reparación automática de conflictos `opencv-python` vs `opencv-python-headless`, descarga atómica de `models/yolo11n-pose.pt` (`.part` + validación de tamaño/ZIP) y prueba real de carga e inferencia `320×320` sin exponer rutas internas.
- **`install_yolo.sh` / `install_yolo.bat`** *(nuevo / actualizado)*: preparan `backend/.venv`, dependencias base y llaman a `ai/setup_yolo.py --install`.
- **`run.sh` / `run.bat`** *(actualizados)*: implementan dos modos explícitos (`--full` y `--light`, preservando `LATIRA_SKIP_YOLO_SETUP=1` y `LATIRA_MODE`); si falla YOLO en modo completo, informan claramente el error, no declaran éxito y permiten decidir si continuar en modo ligero.
- **`backend/app/main.py`**, **`backend/app/routers/pose.py`**, **`backend/app/services/lati_ai.py`**:
  - CORS parametrizado vía `LATIRA_CORS_ORIGINS` (sin comodín `*`).
  - `_pose_integration_status()` delegado a `ai.setup_yolo.get_yolo_runtime_status()` sin rutas absolutas privadas.
  - `get_lati_llm_status()` reporta explícitamente `"connected"`, `"connection_error"`, `"configured"` o `"not_configured"`.
- **`frontend/package.json` & `frontend/package-lock.json`**: sustituidas todas las versiones `"latest"` por rangos fijados y verificado `npm ci && npm run build`.
- **`frontend/src/apiConfig.ts`** *(nuevo)* y **`frontend/src/{App.tsx,Modules.tsx,PoseWorkspace.tsx,WorkflowForms.tsx}`**: soporte para `VITE_API_BASE_URL` en despliegues separados y visualización honesta de los 6 estados de integración, modo `full` vs `lightweight` de YOLO Pose, 6 indicadores de diagnóstico Pose, errores de conexión de LÁTI y disponibilidad de voz en el navegador.
- **`render.yaml`**, **`.env.example`**, **`.gitignore`**, **`models/README.md`**.
- **Nuevas pruebas automatizadas**: `ai/tests/test_setup_yolo.py` y `backend/tests/test_stabilization_security.py`.
- **Documentación actualizada y añadida**: `README.md`, `docs/INSTRUCCIONES_DE_EJECUCION.md`, `docs/fase2/FASE2_INFORME_TECNICO.md`, `docs/INFORME_ESTABILIZACION_FINAL.md`, `docs/INFORME_INSTALACION_REPRODUCIBLE.md`, `docs/INFORME_AUDITORIA_RENDER.md`, `docs/GUIA_INSTALACION.md`, `docs/GUIA_INSTALACION_YOLO_POSE.md`, `docs/GUIA_DEMO_JURADO.md` y `docs/CAMBIOS_FINALES.md`.

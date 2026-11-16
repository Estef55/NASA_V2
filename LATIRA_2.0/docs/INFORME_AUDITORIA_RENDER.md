# Informe de Auditoría de Despliegue en Render — LÁTIRA 2.0

**Estado real del despliegue:** **NO desplegado en Render en esta sesión** (este entorno de auditoría no cuenta con credenciales ni acceso a una cuenta de Render). Este informe documenta la auditoría técnica completa de compatibilidad, los ajustes ya incorporados en el código (`render.yaml`, CORS, `VITE_API_BASE_URL`) y la arquitectura recomendada para producción.

---

## 1. Cambios de compatibilidad ya aplicados en el proyecto

1. **CORS configurable (`backend/app/main.py`)**: lee la variable `LATIRA_CORS_ORIGINS` (lista separada por comas; descarta el comodín `*` al usar credenciales) en lugar de aceptar únicamente `localhost:5173`.
2. **Base URL del frontend en compilación (`frontend/src/apiConfig.ts`)**: `App.tsx`, `Modules.tsx`, `PoseWorkspace.tsx` y `WorkflowForms.tsx` construyen todas las rutas mediante `apiUrl('/api/...')`, utilizando `import.meta.env.VITE_API_BASE_URL` cuando el frontend estático (Static Site) se sirve desde un dominio distinto al backend FastAPI.
3. **Blueprint inicial incluido (`render.yaml`)**: define dos servicios listos para importar en Render:
   - `latira-backend` (`runtime: python`, `backend/`, `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, healthcheck `/api/health`).
   - `latira-frontend` (`runtime: static`, `frontend/`, `npm ci && npm run build`, `dist`, `VITE_API_BASE_URL`, rewrite SPA `/* -> /index.html`).
4. **Seguridad en producción**: `render.yaml` fija `LATIRA_ENV=production` y `LATIRA_DEMO_LOGIN=false`, bloqueando el acceso sin contraseña (`403`) y deshabilitando el autosembrado de cuentas demo.

---

## 2. Auditoría técnica de memoria, almacenamiento y multimedia

### A. Consumo de memoria de YOLO Pose vs. plan Free / Starter (512 MiB)
- **Medición real en este entorno:** cargar `torch` + `ultralytics` + `yolo11n-pose.pt` y ejecutar una sola inferencia sintética alcanzó **`649,704 KB` (`~634.5 MiB`)** de Peak RSS únicamente en el proceso Python de inferencia. Al sumarle FastAPI/Uvicorn, buffers multipart de carga y procesamiento de fotogramas OpenCV, el servicio conjunto supera **`~723.8 MiB` Peak RSS**.
- **Impacto en Render:** los planes Free y Starter tienen un límite rígido de **512 MiB RAM**. Ejecutar YOLO Pose en el mismo contenedor de 512 MiB provocará errores `Out Of Memory (OOM / SIGKILL)`.
- **Decisión en `render.yaml`:** el Blueprint despliega el **núcleo ligero** (`backend/requirements.txt` sin PyTorch ni Ultralytics), estable dentro de 512 MiB RAM; las rutas `/api/pose/*` informan honestamente `503` / `not_configured` sin bloquear el resto de LÁTIRA 2.0.

### B. Persistencia de SQLite y archivos subidos
- En Render Free el sistema de archivos es **efímero**: cualquier escritura en disco se pierde al reiniciar o redesplegar el contenedor.
- `render.yaml` usa `/tmp/latira_data/...` solo para permitir pruebas iniciales en Free. Para persistencia real en producción se requiere:
  - Adjuntar un **Render Persistent Disk** (plan de pago Starter o superior) montado por ejemplo en `/var/data/latira` y apuntar allí `LATIRA_DB_PATH`, `POSE_STORAGE_DIR`, `POSE_HISTORY_DB` y `LATIRA_THERMAL_DIR`, **o** migrar la capa SQLite a una base administrada (PostgreSQL) si se requiere escalado horizontal.

### C. Requisitos de FFmpeg y sistema operativo (Docker)
- El runtime Python nativo de Render no garantiza `ffmpeg` ni librerías del sistema para procesamiento multimedia avanzado. Si se habilita subida/transcodificación de video Pose (`.mp4` H.264 compatible con navegadores), se recomienda desplegar el servicio de visión mediante **Dockerfile** (`apt-get install -y ffmpeg libgl1` si hiciera falta, aunque con `opencv-python-headless` no se requiere X11).

---

## 3. Análisis comparativo: Núcleo ligero vs. Servicio de visión desacoplado

| Aspecto | Opción A — Núcleo ligero en Render (en `render.yaml`) | Opción B — Servicio de visión YOLO Pose desacoplado |
|---|---|---|
| **Plan / Memoria mínima** | Free o Starter (`512 MiB` RAM) suficiente para API + React Static Site. | Requiere servicio independiente con al menos **`2 GB` RAM** (Render Standard, desde ~$25/mes) o GPU/Cloud Run/HF Space dedicado. |
| **API / Contrato** | El mismo backend atiende todo y devuelve `503` / `not_configured` en `/api/pose/*`. | El backend principal reenvía `POST /api/pose/frame` y `/process` (o el frontend apunta `POSE_SERVICE_URL`) al microservicio FastAPI + `ai/setup_yolo.py` con autenticación compartida (token/secret interno HMAC o JWT). |
| **Variables de entorno extra** | `LATIRA_CORS_ORIGINS`, `VITE_API_BASE_URL`, `GEMINI_API_KEY`. | Añadir `POSE_SERVICE_URL`, `POSE_SERVICE_SHARED_SECRET`, `YOLO_POSE_MODEL=/app/models/yolo11n-pose.pt`, `POSE_MAX_UPLOAD_BYTES`. |
| **Almacenamiento temporal** | No almacena videos pesados si Pose está inactivo. | Limpieza estricta de `uploads/` en `finally:` + retención automática o almacenamiento externo (S3/R2) para videos anotados si no hay Persistent Disk. |
| **Manejo de errores** | Inmediato (`503` honesto). | Timeouts explícitos (`30–120s`), circuito de respaldo devolviendo `503` si el microservicio de visión está dormido o saturado, sin colgar las rutas clínicas de LÁTIRA. |

---

## 4. Pasos pendientes que debe ejecutar el usuario para desplegar en Render

1. Subir la carpeta limpia `LATIRA_2.0/` a un repositorio Git (por ejemplo GitHub).
2. En Render Dashboard, elegir **New -> Blueprint** y seleccionar el repositorio con `render.yaml` (o crear los dos servicios manualmente: Web Service Python en `backend/` y Static Site en `frontend/`).
3. En **`latira-frontend`**, configurar `VITE_API_BASE_URL` con la URL HTTPS asignada por Render a `latira-backend` (ej. `https://latira-backend.onrender.com`) y lanzar el build (`npm ci && npm run build`).
4. En **`latira-backend`**, configurar:
   - `LATIRA_CORS_ORIGINS` con la URL HTTPS exacta de `latira-frontend` (ej. `https://latira-frontend.onrender.com`).
   - `GEMINI_API_KEY` (opcional, si se desea IA generativa externa en LÁTI).
   - `LATIRA_DEMO_PASSWORD` solo si se desea sembrar cuentas iniciales en una base vacía, o crear usuarios reales mediante script/administración.
5. Verificar `https://<backend-url>/api/health` y el acceso HTTPS completo (obligatorio para cámara y micrófono en navegadores). Si se requiere YOLO Pose en producción, actualizar el servicio de visión a un plan con **2 GB RAM** (Dockerfile con `ffmpeg` + `./install_yolo.sh`).

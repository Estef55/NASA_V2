# Estado técnico de API y servicios — LÁTIRA 2.0

Base URL local de desarrollo: `http://127.0.0.1:8000` (OpenAPI interactiva en `/docs`). Todas las rutas salvo `/api/health`, `/api/auth/login`, `/api/auth/demo-profiles` y `/api/auth/demo-login` (esta última habilitada solo con `LATIRA_ENV=demo`) requieren `Authorization: Bearer <token>`.

## Rutas principales implementadas

- **Autenticación y sesión**: `POST /api/auth/login`, `GET /api/auth/demo-profiles`, `POST /api/auth/demo-login`, `GET /api/me`, `POST /api/auth/logout`.
  - En producción (`LATIRA_ENV=production`, valor predeterminado), el acceso sin contraseña está deshabilitado (`403`) y se exige usuario y contraseña con hashes PBKDF2-SHA256 con sal aleatoria por usuario.
  - En entorno de demostración (`LATIRA_ENV=demo` y `LATIRA_DEMO_LOGIN!=false`), `POST /api/auth/demo-login` resuelve en el backend el perfil seleccionado (`astronaut`, `medic`, `admin`) hacia su cuenta demo y conserva intactas las sesiones, RBAC y asignaciones.
  - Revocación explícita de tokens en cierre de sesión y automáticamente en `PATCH /api/admin/users/{username}` cuando cambia contraseña, rol, `astronaut_id` o estado `active`.
- **Monitoreo personal y demo aislada**:
  - `POST /api/metrics`: registra mediciones reales (`demo=0`) con validación de rangos y campos obligatorios (`source`, `unit`, `recorded_at`), y evalúa automáticamente `create_deviation_alert`.
  - `GET /api/metrics`: devuelve registros del astronauta autenticado o de los astronautas asignados al médico.
  - `GET /api/baseline`: calcula línea base individual por indicador (`minimum_samples=3`). Selecciona automáticamente modo real o demo según la última métrica del astronauta (o parámetro explícito `?demo=true|false`).
  - `POST /api/demo/start`, `POST /api/demo/next`, `POST /api/demo/reset`, `GET /api/demo`: estado y registros demo aislados por `astronaut_id` (`demo_owner_state`).
- **Chequeo diario y LÁTI (Voz + IA generativa externa)**:
  - `POST /api/checkins` y `GET /api/checkins`: guardan autorreportes (`fatigue`, `mood`, `note`), registran resumen completo en `conversations` (`input_mode='text'`) y devuelven orientación no diagnóstica con `origin: "rules_local"`.
  - `GET /api/lati/status`: devuelve el estado real del modelo generativo externo (`configured`, `connected`, `provider`, `model`, `verification_status`, `last_error` sin exponer claves) para `astronaut`, `medic` y `admin`.
  - `POST /api/lati/chat` y `GET /api/conversation`: aceptan `input_mode` (`"text"` | `"voice"`) y `client_message_id` (deduplicación ante reintentos). Las consultas personales (métricas, línea base, chequeos, alertas abiertas) se resuelven localmente con datos del astronauta autenticado sin enviar telemetría privada al proveedor externo; las consultas científicas NASA/CSA usan `ai/nasa_sources.py`; la conversación general usa el adaptador `backend/app/services/lati_ai.py` (Google AI Studio Gemini o endpoint compatible OpenAI) con contexto de sesión sanitizado y respaldo local controlado (`context_source: "local_fallback"`) si el proveedor falla o no hay clave configurada.
- **Alertas y seguimiento médico**:
  - `GET /api/alerts`: lista alertas del astronauta o tripulación asignada, adjuntando `followups` directamente en cada elemento.
  - `POST /api/alerts/{alert_id}/followups`: restringido a `medic` asignado al astronauta; registra seguimiento y actualiza estado a `review`.
- **Administración y RBAC**:
  - `GET /api/admin/users`, `POST /api/admin/users`, `PATCH /api/admin/users/{username}`.
  - `GET /api/admin/assignments`, `POST /api/admin/assignments`, `DELETE /api/admin/assignments/{medic_username}/{astronaut_id}`.
  - `GET /api/admin/astronauts`, `GET /api/admin/astronauts/{astronaut_id}`, `GET /api/admin/reports/astronauts.csv` (con filtro `astronaut_id` y `demo`).
  - `GET /api/admin/audit`, `GET /api/integrations` (reporta estado real de `thermography`, `nasa`, `pose` y `lati_llm`), `POST /api/integrations/lati/verify` (verificación real en vivo restringida a `admin`).
  - Aislamiento clínico estricto: `admin` recibe `403` en métricas, alertas, seguimientos, línea base, conversaciones y termografía.
- **YOLO Pose**: `/api/pose/status`, `/api/pose/frame`, `/api/pose/live/complete`, `/api/pose/process`, `/api/pose/history`, `/api/pose/history/{analysis_id}/video`, `DELETE /api/pose/history/{analysis_id}`. Gestionado por `ai/setup_yolo.py` con persistencia explícita de modo (`data/pose_mode.json` mediante `--enable` / `--disable`) y verificación real de carga e inferencia `320×320`. En modo ligero (`lightweight`), no carga PyTorch ni pesos `.pt` aunque existan en el entorno y devuelve `503` / `not_configured`; además `ai/yolo_video.py` valida existencia e integridad ZIP/tamaño de los pesos antes de instanciar `YOLO(...)` y limpia archivos temporales/huérfanos ante errores.
- **Utilidad de demostración (`backend/app/demo_tools.py`)**: CLI local (`prepare`, `show`, `reset`) bloqueada estrictamente fuera de `LATIRA_ENV=demo` (o cuando `LATIRA_DEMO_LOGIN=false`), que genera contraseñas aleatorias criptográficas de 24 caracteres compatibles con `PBKDF2-SHA256`, preserva cuentas y datos reales (`demo=0`) sin sobrescribir usuarios existentes, y limpia `followups` demo antes de `alerts`/`metrics` preservando la integridad referencial SQLite.
- **Termografía**: `POST /api/thermography/upload`, `GET /api/thermography/history`, `GET /api/thermography/image/{image_id}`. Valida extensión, firma binaria y tamaño (`10 MiB`), sin estimar temperatura central.
- **NASA y CSA**: `GET /api/integrations/nasa`, `GET /api/integrations/nasa/sources`, `GET /api/integrations/nasa/sources/{source_id}`, `GET /api/integrations/nasa/data`, `POST /api/integrations/nasa/refresh` (lista blanca oficial de dominios y separación estricta respecto a la línea base personal). No existe conexión a sensores espaciales ni dispositivos médicos certificados.

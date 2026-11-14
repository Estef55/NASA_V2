# Estado técnico de API y servicios — LÁTIRA 2.0

Base URL local de desarrollo: `http://127.0.0.1:8000` (OpenAPI interactiva en `/docs`). Todas las rutas salvo `/api/health` y `/api/auth/login` requieren `Authorization: Bearer <token>`.

## Rutas principales implementadas

- **Autenticación y sesión**: `POST /api/auth/login`, `GET /api/me`, `POST /api/auth/logout`.
  - Hashes PBKDF2-SHA256 con sal aleatoria por usuario.
  - Revocación explícita de tokens en cierre de sesión y automáticamente en `PATCH /api/admin/users/{username}` cuando cambia contraseña, rol, `astronaut_id` o estado `active`.
- **Monitoreo personal y demo aislada**:
  - `POST /api/metrics`: registra mediciones reales (`demo=0`) con validación de rangos y campos obligatorios (`source`, `unit`, `recorded_at`), y evalúa automáticamente `create_deviation_alert`.
  - `GET /api/metrics`: devuelve registros del astronauta autenticado o de los astronautas asignados al médico.
  - `GET /api/baseline`: calcula línea base individual por indicador (`minimum_samples=3`). Selecciona automáticamente modo real o demo según la última métrica del astronauta (o parámetro explícito `?demo=true|false`).
  - `POST /api/demo/start`, `POST /api/demo/next`, `POST /api/demo/reset`, `GET /api/demo`: estado y registros demo aislados por `astronaut_id` (`demo_owner_state`).
- **Chequeo diario y LÁTI**:
  - `POST /api/checkins` y `GET /api/checkins`: guardan autorreportes (`fatigue`, `mood`, `note`), registran resumen completo en `conversations` y devuelven orientación no diagnóstica con `origin: "rules_local"`.
  - `POST /api/lati/chat` y `GET /api/conversation`: consultan exclusivamente los registros reales del astronauta autenticado (últimas métricas, línea base, chequeos recientes, hasta 3 alertas abiertas) y referencias verificadas NASA/CSA con detección por límites de palabra (`\b...\b`), registrando auditoría `lati_chat`.
- **Alertas y seguimiento médico**:
  - `GET /api/alerts`: lista alertas del astronauta o tripulación asignada, adjuntando `followups` directamente en cada elemento.
  - `POST /api/alerts/{alert_id}/followups`: restringido a `medic` asignado al astronauta; registra seguimiento y actualiza estado a `review`.
- **Administración y RBAC**:
  - `GET /api/admin/users`, `POST /api/admin/users`, `PATCH /api/admin/users/{username}`.
  - `GET /api/admin/assignments`, `POST /api/admin/assignments`, `DELETE /api/admin/assignments/{medic_username}/{astronaut_id}`.
  - `GET /api/admin/astronauts`, `GET /api/admin/astronauts/{astronaut_id}`, `GET /api/admin/reports/astronauts.csv` (con filtro `astronaut_id` y `demo`).
  - `GET /api/admin/audit`, `GET /api/integrations` (reporta estado real de `thermography`, `nasa`, `pose` y `lati_llm`).
  - Aislamiento clínico estricto: `admin` recibe `403` en métricas, alertas, seguimientos, línea base y termografía.
- **YOLO Pose**: `/api/pose/status`, `/api/pose/frame`, `/api/pose/live/complete`, `/api/pose/process`, `/api/pose/history`, `/api/pose/history/{analysis_id}/video`, `DELETE /api/pose/history/{analysis_id}`. Devuelve `503` cuando faltan dependencias o pesos `.pt`, y limpia archivos temporales/huérfanos ante errores.
- **Termografía**: `POST /api/thermography/upload`, `GET /api/thermography/history`, `GET /api/thermography/image/{image_id}`. Valida extensión, firma binaria y tamaño (`10 MiB`), sin estimar temperatura central.
- **NASA y CSA**: `GET /api/integrations/nasa`, `GET /api/integrations/nasa/sources`, `GET /api/integrations/nasa/sources/{source_id}`, `GET /api/integrations/nasa/data`, `POST /api/integrations/nasa/refresh` (lista blanca oficial de dominios y separación estricta respecto a la línea base personal).

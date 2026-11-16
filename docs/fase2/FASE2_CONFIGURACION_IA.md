# Configuración del modelo generativo externo e interacción por voz — LÁTIRA 2.0 (Fase 2)

## 1. Arquitectura de seguridad (solo servidor)

- Toda comunicación con el proveedor generativo externo se ejecuta exclusivamente en el backend FastAPI (`backend/app/services/lati_ai.py`).
- **Ninguna clave API se almacena en el código, ni se incluye en el frontend compilado (`frontend/dist/`), ni se solicita al usuario desde la interfaz web.**
- El navegador únicamente se comunica con las rutas protegidas de LÁTIRA (`/api/lati/status`, `/api/lati/chat`, `/api/conversation`, `/api/integrations/lati/verify`) mediante el token de sesión del usuario autenticado.

---

## 2. Variables de entorno admitidas

Define las variables en la terminal del servidor antes de iniciar el backend (`LATIRA_2.0` no autocarga archivos `.env`):

| Variable | Uso | Valor por defecto |
|---|---|---|
| `GEMINI_API_KEY` | Clave API de Google AI Studio (Gemini). También admite `GOOGLE_API_KEY` o `LATIRA_LLM_API_KEY`. | *(vacío — modo local)* |
| `LATIRA_LLM_API_KEY` | Alternativa genérica para clave API (Gemini o endpoint compatible con OpenAI). | *(vacío)* |
| `LATIRA_LLM_BASE_URL` | Opcional. Si está vacío y hay clave Gemini, usa `https://generativelanguage.googleapis.com/v1beta`. Para otro proveedor compatible con OpenAI, define la URL base (ej. `https://.../v1`). | Gemini API (`v1beta`) |
| `LATIRA_LLM_MODEL` | Modelo generativo a invocar (también lee `GEMINI_MODEL`). | `gemini-4-hydrogen` (Gemini) |
| `LATIRA_LLM_PROVIDER` | Opcional (`gemini` u `openai_compatible`) para forzar el formato de API. | Autodetección según URL/clave |
| `LATIRA_LLM_TIMEOUT_SECONDS` | Tiempo máximo de espera HTTP (entre `2` y `60` segundos). | `15` |

### Ejemplo rápido con Google AI Studio (Gemini)

**Linux / macOS:**
```bash
export LATIRA_ENV="demo"
export GEMINI_API_KEY="TU_CLAVE_DE_GOOGLE_AI_STUDIO"
export LATIRA_LLM_MODEL="gemini-4-hydrogen"
cd LATIRA_2.0
./run.sh
```

**Windows (PowerShell):**
```powershell
$env:LATIRA_ENV = "demo"
$env:GEMINI_API_KEY = "TU_CLAVE_DE_GOOGLE_AI_STUDIO"
$env:LATIRA_LLM_MODEL = "gemini-4-hydrogen"
cd LATIRA_2.0
.\run.bat
```

---

## 3. Verificación real y comportamiento sin clave API

- **Sin clave configurada**:
  - `GET /api/lati/status` y `GET /api/integrations` informan honestamente `status: "not_configured"` y `mode: "rules_local"`.
  - LÁTI responde mediante reglas locales determinísticas (`origin: "rules_local"`) y catálogo científico verificado NASA/CSA, sin simular jamás una conexión externa.
- **Con clave configurada**:
  - La persona administradora (`admin`) puede ejecutar una prueba real en vivo desde **Integraciones -> LÁTI · IA generativa -> Verificar conexión** (`POST /api/integrations/lati/verify`).
  - El adaptador envía una solicitud mínima real al modelo configurado y actualiza `verification_status`: `connected`, `auth_error` (401/403), `model_not_found` (404), `quota_exceeded` (429), `timeout` o `network_error`.
  - Ante cualquier error del proveedor externo, LÁTI activa un **respaldo local controlado** (`origin: "rules_local"`, `context_source: "local_fallback"`, `fallback_used: true`) e informa el fallo sin exponer jamás la clave API en errores, registros ni base de datos.

---

## 4. Aislamiento de privacidad y alcance no médico

- Las consultas sobre métricas personales guardadas (`sleep`, `heart_rate`, `fatigue`, `mood`), `baseline` / `línea base`, `checkins` y `alerts` se resuelven **localmente** sobre SQLite para el `astronaut_id` autenticado (`rules_local`) y **nunca** se envían al proveedor externo.
- El historial multi-turno enviado al modelo externo para continuidad conversacional filtra explícitamente los turnos clínicos previos (`context_source == 'authenticated_astronaut_records'`) y los resúmenes automáticos de chequeo diario.
- El prompt de sistema instruye a LÁTI a mantener su identidad no diagnóstica, no prescribir tratamientos, responder en el idioma activo (`es` / `en`) y usar frases claras optimizadas para síntesis de voz.

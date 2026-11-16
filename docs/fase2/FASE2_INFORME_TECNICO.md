# Informe Técnico de Cierre — Fase 2 (LÁTI con Voz e IA Generativa Externa)

**Proyecto:** LÁTIRA 2.0
**Base de partida:** `LATIRA_2.0_FASE1_DEMO_LOGIN.zip`
**Alcance:** Integración real de voz en el navegador (STT/TTS), adaptador server-side para modelo generativo externo (`lati_ai.py`), aislamiento de privacidad clínica y persistencia de conversaciones.

---

## 1. Arquitectura implementada

1. **Interacción por voz en el navegador (`frontend/src/WorkflowForms.tsx`)**:
   - **Entrada por micrófono (STT)**: utiliza `window.SpeechRecognition` / `window.webkitSpeechRecognition` bajo control explícito del usuario (botón **Hablar** / **Detener voz**, indicador animado *Escuchando…* y vista previa en vivo). Nunca activa el micrófono automáticamente.
   - **Salida hablada (TTS)**: utiliza `window.speechSynthesis` con cancelación previa (`window.speechSynthesis.cancel()`) para evitar solapamientos, botón global y por burbuja para detener o repetir la lectura, preferencia persistente en `localStorage` (`latira-lati-autospeak`), y limpieza previa de markdown/URLs (`sanitizeTextForSpeech`).
   - **Degradación honesta**: la UI informa explícitamente la disponibilidad real en el navegador (*Voz disponible*, *Solo lectura por voz* o *Voz no disponible*) sin bloquear la conversación escrita.

2. **Adaptador generativo exclusivamente en servidor (`backend/app/services/lati_ai.py`)**:
   - Soporta Google AI Studio / Gemini (`GEMINI_API_KEY`, `GOOGLE_API_KEY` o `LATIRA_LLM_API_KEY`; modelo por defecto `gemini-4-hydrogen`) y endpoints compatibles con OpenAI (`LATIRA_LLM_BASE_URL` + `LATIRA_LLM_API_KEY` + `LATIRA_LLM_MODEL`).
   - Clasifica fallos reales sin simular conexiones: `auth_error` (401/403), `model_not_found` (404), `quota_exceeded` (429), `provider_unavailable` (5xx), `timeout` y `network_error`. Redacta cualquier fragmento de clave API antes de registrar estado o devolver errores.
   - Expone `GET /api/lati/status` (roles autenticados) y `POST /api/integrations/lati/verify` (restringido a `admin` y registrado en auditoría).

3. **Aislamiento de privacidad clínica (`backend/app/routers_extra.py`)**:
   - Las consultas sobre métricas personales (`sleep`, `heart_rate`, `fatigue`, `mood`), línea base, chequeos diarios y alertas abiertas se resuelven localmente (`origin: "rules_local"`, `context_source: "authenticated_astronaut_records"`) sobre los datos del `astronaut_id` autenticado, **sin enviarse nunca al proveedor generativo externo**.
   - Las consultas científicas NASA/CSA se resuelven desde `ai/nasa_sources.py` (`context_source: "verified_nasa_csa_references"`).
   - Antes de invocar al modelo generativo externo (`context_source: "external_generative_model"`), el historial multi-turno filtra explícitamente cualquier turno con `context_source == "authenticated_astronaut_records"` y los resúmenes automáticos de chequeos diarios.
   - Si no hay clave configurada (`context_source: "local_rules_unconfigured"`) o si el proveedor falla (`context_source: "local_fallback"`, `fallback_used: true`), LÁTI responde con respaldo local controlado no diagnóstico.

4. **Persistencia e idempotencia (`backend/app/main.py`)**:
   - Migración no destructiva en `init()` añadiendo a `conversations` las columnas `input_mode`, `context_source`, `model`, `client_message_id` y el índice único parcial `idx_conversations_client_msg` sobre `(astronaut_id, role, client_message_id)` para evitar duplicados ante reintentos.

---

## 2. Verificación automatizada (`backend/tests/test_lati_phase2.py`)

Casos cubiertos en `test_lati_phase2.py` (ejecutados en entorno aislado mediante `_db_isolation`):
- Estado honesto `not_configured` / `rules_local` sin clave API y conservación de `input_mode="voice"`.
- Flujo multi-turno con Gemini (simulado vía callback `http_post` controlado en pruebas) verificando que las métricas privadas, notas de chequeo y alertas secretas del astronauta **no** se filtran en el cuerpo enviado al proveedor externo.
- Soporte de endpoint compatible OpenAI (`LATIRA_LLM_BASE_URL`).
- Control de acceso a `POST /api/integrations/lati/verify` (exclusivo `admin`; rechazo `403` para astronauta y médico).
- Respaldo local controlado (`fallback_used=True`) ante errores HTTP 401/429 y timeout, con redacción de secretos.
- Deduplicación idempotente por `client_message_id` y aislamiento RBAC por `astronaut_id`.
- Migración no destructiva de bases SQLite previas a Fase 2.

---

## 3. Limitaciones conocidas

- El reconocimiento de voz (`SpeechRecognition`) depende del soporte del navegador cliente (disponible en Chrome y Edge modernos en `localhost` o HTTPS; no disponible en todos los navegadores ni sin permiso de micrófono).
- La activación real del proveedor externo depende de definir `GEMINI_API_KEY` o `LATIRA_LLM_API_KEY` en el entorno del servidor; las pruebas automatizadas no invocan APIs externas de pago sin credenciales del usuario.

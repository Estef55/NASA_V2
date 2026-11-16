# Registro de cambios — Fase 2 (LÁTI Voz e IA Generativa Externa)

Base de partida obligatoria: `LATIRA_2.0_FASE1_DEMO_LOGIN.zip`.

## 1. Archivos añadidos

- `backend/app/services/lati_ai.py`: adaptador server-side para modelo generativo externo (Google AI Studio / Gemini REST API con modelo por defecto `gemini-4-hydrogen` y soporte para endpoints compatibles OpenAI), clasificación explícita de errores (`401/403`, `404`, `429`, `timeout`, `network_error`), redacción de secretos, verificación en vivo y constructor de prompt no médico bilingüe.
- `backend/tests/test_lati_phase2.py`: suite de pruebas unitarias y de integración para estado no configurado, Gemini multi-turno, aislamiento estricto de privacidad clínica, endpoint compatible OpenAI, verificación admin-only, fallback honesto ante errores HTTP/timeout, persistencia de `input_mode` (`text`/`voice`), deduplicación por `client_message_id`, RBAC y migración no destructiva de SQLite.
- `docs/fase2/FASE2_INFORME_TECNICO.md`: informe técnico de auditoría, arquitectura, pruebas reales y limitaciones de Fase 2.
- `docs/fase2/FASE2_CONFIGURACION_IA.md`: guía de configuración segura de variables de entorno en servidor.
- `docs/fase2/FASE2_GUIA_DEMO_LATI.md`: guía paso a paso para demostración de voz y texto de LÁTI.
- `docs/fase2/FASE2_CAMBIOS.md`: inventario detallado de cambios y limpieza documental.

## 2. Archivos modificados

- `backend/app/main.py`:
  - Migración no destructiva de la tabla `conversations` en `init()` añadiendo `input_mode` (`'text'` por defecto), `context_source`, `model`, `client_message_id` e índice único parcial `idx_conversations_client_msg`.
  - Delegación de `_lati_llm_status()` a `lati_ai.get_lati_llm_status()`.
  - Nuevas rutas `GET /api/lati/status` (roles autenticados) y `POST /api/integrations/lati/verify` (exclusiva `admin`, auditada).
  - Registro explícito de `input_mode='text'` y `context_source='authenticated_astronaut_records'` en `POST /api/checkins`.
- `backend/app/routers_extra.py`:
  - Ampliación de `ChatMessage` con `input_mode: Literal['text', 'voice'] = 'text'` y `client_message_id`.
  - Deduplicación idempotente de mensajes mediante `client_message_id`.
  - Separación estricta de consultas personales (`authenticated_astronaut_records`) y científicas NASA/CSA (`verified_nasa_csa_references`) respecto al modelo generativo externo (`external_generative_model`).
  - Construcción de historial multi-turno sanitizado (excluye registros clínicos y chequeos diarios antes de llamar al proveedor externo) y respaldo local controlado (`local_fallback`) ante fallos.
- `frontend/src/WorkflowForms.tsx`:
  - Integración de reconocimiento de voz (`SpeechRecognition` / `webkitSpeechRecognition`) dentro del chat `LatiChat` con botón **Hablar**, indicador visual **Escuchando…**, vista previa en vivo, botón **Detener voz**, opción de envío automático y mensajes claros ante navegador incompatible o permiso denegado.
  - Integración de síntesis de voz (`window.speechSynthesis`) con cancelación previa para evitar solapamiento, botón global y por mensaje para escuchar/detener, silenciado persistente y limpieza de código markdown/URLs antes de leer.
  - Visualización de modalidad (**Voz** / **Texto**), procedencia real (**Gemini**, **Modelo externo**, **Reglas locales**, **Respaldo local**), protección contra doble envío y estado real del modelo desde `/api/lati/status`.
- `frontend/src/workflow.css`: estilos oscuros coherentes con LÁTIRA 2.0 para controles de voz, indicador pulsante de escucha, insignias de modalidad y estado de IA.
- `frontend/src/App.tsx`: cancelación de `window.speechSynthesis` al cerrar sesión y tarjeta **LÁTI · IA generativa** en **Integraciones** con botón admin de verificación en vivo.
- `.env.example`, `README.md`, `frontend/README.md`, `docs/ESTADO_TECNICO.md`, `docs/INSTRUCCIONES_DE_EJECUCION.md`, `docs/MANUAL_DEMO.md`, `docs/MANUAL_USUARIO.md`: actualización alineada con Fase 1 y Fase 2.

## 3. Archivos obsoletos retirados del paquete limpio (Tarea 6)

*(Respaldo previo conservado fuera del entregable; documentación científica NASA/CSA `docs/FASE_INTEGRACION_NASA_LATIRA_2.0.md` conservada íntegra.)*

- `docs/FASE_CIERRE_TECNICO_LATIRA_2.0.md`: retirado por contener estado histórico contradictorio (afirmaba que NASA y `LATIRA_LLM_*` estaban pendientes y describía inicio de sesión previo a Fase 1).
- `docs/INFORME_PRUEBAS.md`: retirado por reflejar conteos y configuración previos a Fase 1 y Fase 2; reemplazado por `docs/fase2/FASE2_INFORME_TECNICO.md`.

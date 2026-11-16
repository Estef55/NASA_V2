# Guía de Demostración para Jurado — LÁTIRA 2.0

*Prototipo académico de apoyo al bienestar en misiones espaciales. No es un dispositivo médico ni sustituye evaluación clínica.*

---

## 1. Preparación previa (antes de presentar)

1. Descomprime `LATIRA_2.0_FINAL.zip` y entra en `LATIRA_2.0/`.
2. Define el modo demostración (los scripts `run.sh` y `run.bat` activan `LATIRA_ENV=demo` automáticamente si no se ha fijado `production`):
   - **Con YOLO Pose (recomendado para demostrar cámara/video real):** ejecuta `./run.sh --full` (Linux/macOS) o `.\run.bat --full` (Windows).
   - **Solo núcleo ligero (sin cámara Pose):** ejecuta `./run.sh --light` o `.\run.bat --light`.
   - **Opcional — LÁTI con Gemini en vivo:** exporta `GEMINI_API_KEY` antes de lanzar el script. Sin clave, LÁTI opera con reglas locales y respaldo honesto.
3. Abre `http://127.0.0.1:5173` en **Google Chrome** o **Microsoft Edge** (contexto seguro necesario para micrófono y cámara web).

---

## 2. Guion sugerido de demostración (5 minutos)

### Paso 1 — Inicio de sesión con tarjetas de perfil y bilingüismo
1. En la pantalla de inicio de sesión, cambia entre **Español / English** en la esquina superior derecha para mostrar el soporte bilingüe completo.
2. Señala las **tres tarjetas seleccionables** (`Astronauta`, `Médico`, `Administrador`), explicando que el acceso sin contraseña solo está activo porque el servidor está en `LATIRA_ENV=demo` y conserva los permisos RBAC originales.
3. Selecciona **Astronauta** (`AST-001`) y entra.

### Paso 2 — Flujo clínico personal, línea base y alertas explicables
1. En **Resumen**, muestra el estado `LIVE MONITORING` y opcionalmente ejecuta el **Escenario demo** (`Iniciar escenario` -> avanzar días -> `Reiniciar`) aclarando que `demo=1` nunca contamina los registros reales.
2. En **Chequeo diario**, guarda fatiga y ánimo: LÁTI responde al instante con orientación local no diagnóstica.
3. En **Registro real**, guarda 3 mediciones normales (`demo=0`) para completar la **Línea base personal** (`SUFFICIENT`, umbral configurable `20%`) y una 4.ª medición con desviación >= `20%` para mostrar la **alerta explicable automática** (no diagnóstica).

### Paso 3 — LÁTI con voz e IA generativa y privacidad clínica
1. Entra en **LÁTI**: muestra el estado real del modelo en la cabecera (*Modelo externo conectado/configurado* o *Reglas locales*) y el estado de voz del navegador (*Voz disponible*).
2. Pulsa **Hablar** para dictar por micrófono (o escribe en texto), observa el indicador *Escuchando…* y la lectura hablada con botón **Detener voz**.
3. Pregunta por tus métricas/alertas (*"¿Cómo está mi línea base?"*): destaca que se resuelve **localmente en el servidor (`rules_local`)** sin enviar telemetría privada a modelos externos.
4. Haz una pregunta general de bienestar o una consulta científica NASA/CSA.

### Paso 4 — YOLO Pose e imagen térmica (sin simulaciones)
1. Entra en **Movimiento (Pose)**:
   - Muestra el estado real (**Modo completo · YOLO Pose disponible** o **Modo ligero · no disponible**).
   - Con cámara autorizada en **Cámara en vivo**, **Grabar** o **Subir video**, muestra los puntos clave geométricos y el resumen comprensible (*Observaciones interpretadas*, *Limitaciones*), subrayando que no es diagnóstico.
2. En **Imagen térmica**, muestra la carga/captura visual y el aviso explícito de que una cámara convencional no mide temperatura corporal central.

### Paso 5 — Vista de Médico y Administrador (RBAC e Integraciones)
1. Cierra sesión y entra como **Médico**: entra en **Tripulación asignada (`AST-001`)**, alterna entre **Registros reales** y **Demo ficticia**, descarga el reporte CSV y agrega una nota de seguimiento sobre la alerta (pasa a `En revisión`).
2. Cierra sesión y entra como **Administrador**: confirma el distintivo `RBAC ISOLATED` (sin pestañas clínicas). En **Integraciones**, muestra las tarjetas de **NASA & CSA**, **LÁTI · IA generativa**, **Estimación de pose** (con los 6 indicadores reales) y **Termografía**, además del panel **Ciencia NASA y CSA** con refresco en vivo de OSDR si hay internet.

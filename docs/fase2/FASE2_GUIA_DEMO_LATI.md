# Guía de demostración de LÁTI por voz y texto — LÁTIRA 2.0 (Fase 2)

## 1. Requisitos del navegador para la demo de voz

- Para probar reconocimiento de voz (`SpeechRecognition` / `webkitSpeechRecognition`) y síntesis de voz (`speechSynthesis`) en vivo durante la presentación:
  - Utiliza **Google Chrome** o **Microsoft Edge** recientes.
  - Abre la aplicación en contexto seguro: `http://127.0.0.1:5173` / `http://localhost:5173` (o `https://...` si se despliega en red).
  - Concede permiso de micrófono cuando el navegador lo solicite tras pulsar **Hablar**.
- Si el navegador utilizado no admite Web Speech API (por ejemplo Firefox sin bandera experimental o entorno sin micrófono), LÁTIRA muestra un aviso comprensible y permite continuar la conversación completa mediante texto escrito sin bloqueos.

---

## 2. Flujo paso a paso para el jurado

1. **Acceso de demostración (Fase 1 preservada)**:
   - Inicia LÁTIRA con `./run.sh` (o `.\run.bat`).
   - En la pantalla de inicio de sesión, selecciona **Astronauta** y haz clic en **«Iniciar sesión»**.
2. **Abrir LÁTI en el panel del astronauta**:
   - En la barra lateral izquierda, haz clic en **LÁTI**.
   - Verifica el distintivo de estado en la cabecera del chat:
     - Si `GEMINI_API_KEY` / `LATIRA_LLM_API_KEY` está configurada: muestra **Modelo externo listo** o **Modelo externo activo**.
     - Si no hay clave en el servidor: muestra honestamente **Reglas locales · modelo externo sin configurar**.
3. **Conversación por voz (STT + TTS)**:
   - Haz clic en el botón **Hablar** (ícono de micrófono junto a **Enviar**). *(LÁTI nunca activa el micrófono automáticamente).*
   - Confirma el indicador animado **Escuchando…** y la transcripción en vivo.
   - Pronuncia una frase natural en español o inglés (p. ej. *"Hola LÁTI, ayúdame a relajarme antes de dormir"*).
   - Al terminar la frase o pulsar **Detener voz**, el mensaje se envía a LÁTI y queda registrado con la etiqueta **Voz** en el historial.
   - Si **Voz LÁTI: activa** está habilitado, LÁTI lee automáticamente su respuesta en voz alta sin solapar audios anteriores y omitiendo bloques técnicos o URLs.
   - Puedes pulsar **Detener voz** en la cabecera o en la propia burbuja en cualquier momento, o volver a pulsar **Escuchar** sobre cualquier respuesta previa.
4. **Continuidad multi-turno, texto y consultas personales**:
   - Escribe un mensaje de seguimiento en la misma conversación y pulsa **Enviar** (o `Enter`): queda guardado con etiqueta **Texto**.
   - Pregunta por tus datos reales (*"¿Cómo está mi línea base?"* o *"¿Tengo alertas abiertas?"*): LÁTI responde localmente con tus registros reales aislados (`Reglas locales`), sin exponer telemetría privada al proveedor externo.
   - Cierra sesión (**Salir** en la barra inferior) o recarga el navegador y vuelve a entrar como **Astronauta**: todo el historial (voz, texto y chequeos) permanece intacto y aislado exclusivamente para `AST-001`.
5. **Verificación de aislamiento RBAC y estado de IA (Médico y Administrador)**:
   - Cierra sesión e ingresa como **Médico** o **Administrador**: no tienen acceso a la conversación privada del astronauta.
   - Como **Administrador**, abre **Integraciones** y revisa la tarjeta **LÁTI · IA generativa**; si hay clave configurada, puedes pulsar **Verificar conexión** para validar en vivo la conectividad con el proveedor.

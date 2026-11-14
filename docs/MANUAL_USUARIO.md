# Guía rápida de usuario y demostración

## Acceso
Ejecuta backend y frontend según `README.md` y abre la URL local. En una base nueva, las cuentas de demostración se crean únicamente si `LATIRA_DEMO_PASSWORD` se define antes del primer inicio; la clave no se incluye en el repositorio. No uses usuarios demo en un servidor público.

## Recorrido sugerido
1. Entra con el rol astronauta (`astro_demo`) y revisa el estado del resumen (`LIVE MONITORING` o `DEMO DATA`), los indicadores, la gráfica y la disponibilidad de línea base personal (requiere mínimo 3 muestras por indicador; si hay historial insuficiente, la interfaz lo indica).
2. Opcionalmente inicia el escenario etiquetado `DEMO DATA` / `DEMO FICTICIO` y avanza día a día hasta el día 5 para observar alertas de prueba marcadas como `DEMO`. Reinicia el escenario cuando termines; el estado demo está aislado por astronauta.
3. Completa el **Chequeo diario**; LÁTI responde inmediatamente debajo con orientación local no diagnóstica (`rules_local`) y guarda el intercambio en tu historial.
4. En **Registro real**, ingresa mediciones reales (`demo=0`). A partir del 4.º registro frente a tu línea base previa, cualquier desviación >= 20% genera una alerta explicable no diagnóstica.
5. Cierra sesión; accede con el rol médico (`medic_demo`) y revisa solo astronautas asignados, alternando entre registros reales y demo. Añade una nota de seguimiento en **Alertas y seguimiento**; la alerta pasa a `In review` (`En revisión`) y el astronauta podrá ver esa nota en su panel.
6. Cierra sesión; el rol administrador (`admin_demo`) verifica cuentas, asignaciones e **Integraciones** (incluyendo consulta NASA/CSA y verificación en vivo de OSDR). Las integraciones ausentes o sin hardware se muestran como no conectadas o sin configurar, sin acceso automático a datos clínicos.

## Uso responsable
No ingreses datos identificables reales en esta demo. Sueño, frecuencia cardíaca, fatiga, ánimo y resultados visuales son información sensible. LÁTIRA es un prototipo académico no validado clínicamente. Una alerta solicita revisión humana; no establece un diagnóstico ni prescribe tratamientos.

## Video / pose
Usa exclusivamente videos con consentimiento y autorización. En **Movimiento (Pose)** puedes usar cámara en vivo, grabación o subida de video si el servidor cuenta con dependencias (`ai/requirements.txt`) y pesos (`yolo11n-pose.pt`). Cuando el modelo no está disponible, el sistema informa `not_configured` / `503` y no inventa resultados. Las métricas geométricas de keypoints dependen de cámara, encuadre, oclusiones y calibración; no equivalen a evaluación médica.

## Astronauta: mediciones, LÁTI y termografía
- En «Registro real», ingresa el valor, unidad, origen y fecha/hora del indicador, y guarda solo observaciones reales. Los registros demo y los reales nunca se mezclan en la línea base ni en las tablas activas.
- En «Chequeo diario», registra fatiga y ánimo en las escalas `1–5` (`Bajo` / `Alto`). El chequeo es autorreporte.
- En «LÁTI», la conversación se conserva por cuenta autenticado (`rules_local`). Consulta tus registros reales, línea base, chequeos, alertas abiertas o referencias científicas NASA/CSA sin diagnóstico ni prescripción.
- En «Imagen térmica» se suben o capturan imágenes para revisión visual. Una cámara convencional no estima temperatura corporal central.

## Profesional médico
Selecciona una persona de la lista de **Tripulación asignada**. Revisa sus mediciones reales o demo, estado de línea base por indicador, alertas, seguimientos e historial de Pose/termografía autorizado, o descarga el reporte CSV filtrado. Añade observaciones solo al caso asignado; la restricción se valida también en el backend.

## Administrador
Usa **Administración** para gestionar usuarios, contraseñas, roles y asignaciones médico-astronauta (modificar credenciales o rol revoca sesiones previas del usuario afectado). Consulta **Integraciones** y el panel **Ciencia NASA y CSA** para confirmar estados reales y datos públicos de NASA OSDR, estrictamente separados de la telemetría personal. El rol administrador no tiene acceso a métricas, alertas, chequeos ni termografías clínicas.

## Línea base y reportes
La línea base es individual por astronauta e indicador. Con muestra insuficiente, el sistema lo indica en vez de presentar una referencia confiable. Las alertas son señales exploratorias que necesitan revisión humana. Exporta reportes solo para fines de demostración y conserva sus archivos con cuidado.

## Cierre de sesión y privacidad
El token de acceso se almacena en `localStorage` del navegador. Cierra sesión al terminar la prueba (revoca el token en el servidor), no compartas capturas que revelen identificadores o notas, y elimina la base local de prueba conforme a las reglas de retención. No cargues datos clínicos reales en este prototipo.


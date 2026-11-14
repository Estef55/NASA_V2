# Manual de demostración local — LÁTIRA 2.0

## Preparación

1. Usa un entorno de prueba local y no cargues datos personales reales.
2. Configura una base de datos limpia y una clave demo local segura sin escribirla en archivos del proyecto:
   - Linux / macOS:
     ```bash
     export LATIRA_DB_PATH="/tmp/latira-demo.sqlite3"
     export LATIRA_DEMO_PASSWORD="TuClaveLocalFuerte"
     ```
   - PowerShell (Windows):
     ```powershell
     $env:LATIRA_DB_PATH = "$env:LOCALAPPDATA\Temp\latira-demo.sqlite3"
     $env:LATIRA_DEMO_PASSWORD = Read-Host "Clave local de demo"
     ```
3. Si esa base de datos está vacía, el primer inicio siembra `astro_demo` (`AST-001`), `medic_demo` y `admin_demo` usando `LATIRA_DEMO_PASSWORD`.
4. Inicia backend y frontend siguiendo `docs/INSTRUCCIONES_DE_EJECUCION.md` y confirma `http://127.0.0.1:8000/api/health`.

## Recorrido sugerido

1. **Astronauta (`astro_demo`)**:
   - Inicia sesión y observa el estado inicial `LIVE MONITORING`.
   - Opcionalmente prueba el escenario didáctico (`Start scenario` -> `Next day` hasta día 5 -> `Reset`). El escenario está aislado por astronauta y marcado como `DEMO`.
   - En **Chequeo diario**, selecciona fatiga y ánimo, añade una nota y guarda: LÁTI muestra su orientación local inmediatamente debajo sin salir de la pantalla.
   - En **Registro real**, guarda 3 mediciones reales para construir tu línea base personal (`SUFFICIENT`) y luego una 4.ª medición con variación >= 20% para comprobar la generación automática de una alerta real explicable (no diagnóstica).
   - En **LÁTI**, pregunta por tus indicadores, tu línea base, tu último chequeo o tus alertas abiertas; cambia entre inglés y español.
   - En **Movimiento (Pose)** e **Imagen térmica**, verifica los controles y avisos honestos (sin simular inferencias si YOLO no está configurado ni simular temperatura central).
2. **Personal médico (`medic_demo`)**:
   - Entra en **Tripulación asignada**, selecciona `AST-001`, alterna entre **Registros reales** y **Demo ficticia**, y descarga el reporte CSV.
   - En **Alertas y seguimiento**, agrega una nota de seguimiento sobre la alerta real y confirma que pasa a estado `IN REVIEW` (`En revisión`).
3. **Administrador (`admin_demo`)**:
   - Confirma el distintivo `RBAC ISOLATED` (sin pestañas clínicas).
   - En **Administración**, crea un usuario astronauta de prueba (`AST-002`), gestiona asignaciones y consulta **Integraciones** (incluyendo verificación en vivo de NASA OSDR si hay acceso de red).
4. Cierra todas las sesiones con el botón de perfil antes de finalizar.

## Comprobaciones y límites

- Nunca incluyas claves reales en capturas, informes ni paquetes ZIP.
- El escenario demo de 5 días utiliza datos ficticios y nunca se mezcla con los registros reales en la línea base ni en los reportes reales.
- Si YOLO Pose no tiene dependencias/pesos instalados o no hay cámara conectada, la aplicación informa claramente la ausencia del servicio sin fabricar datos.

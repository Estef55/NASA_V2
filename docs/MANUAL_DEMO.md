# Manual de demostración local — LÁTIRA 2.0

## Preparación

1. Usa un entorno de prueba local y no cargues datos personales reales.
2. Configura una base de datos limpia y habilita explícitamente el modo de demostración (`LATIRA_ENV=demo` — los scripts `run.sh` y `run.bat` lo activan por defecto; en producción debe mantenerse `LATIRA_ENV=production`):
   - Linux / macOS:
     ```bash
     export LATIRA_ENV="demo"
     export LATIRA_DB_PATH="/tmp/latira-demo.sqlite3"
     ```
   - PowerShell (Windows):
     ```powershell
     $env:LATIRA_ENV = "demo"
     $env:LATIRA_DB_PATH = "$env:LOCALAPPDATA\Temp\latira-demo.sqlite3"
     ```
3. Al iniciar en modo `demo`, el backend verifica y siembra de forma segura cualquier cuenta de demostración faltante (`astro_demo` con `AST-001`, `medic_demo` asignada a `AST-001`, y `admin_demo`) sin borrar datos ni reiniciar la base existente.
   Si además necesitas iniciar sesión mediante usuario/contraseña local o preparar días de escenario de antemano, utiliza la utilidad segura `app.demo_tools` (nunca expongas ni publiques las contraseñas generadas en capturas o informes):
   ```powershell
   # Windows PowerShell (desde LATIRA_2.0\)
   $env:LATIRA_ENV = "demo"; $env:PYTHONPATH = "backend"
   backend\.venv\Scripts\python.exe -m app.demo_tools prepare --days 3
   backend\.venv\Scripts\python.exe -m app.demo_tools show
   # Para limpiar únicamente datos demo (demo=1) sin tocar registros ni cuentas reales:
   backend\.venv\Scripts\python.exe -m app.demo_tools reset
   ```
4. Inicia backend y frontend (`./run.sh` o `.\run.bat`, o manualmente según `docs/INSTRUCCIONES_DE_EJECUCION.md`) y confirma `http://127.0.0.1:8000/api/health`.

## Recorrido sugerido

1. **Astronauta (`astro_demo`)**:
   - En la pantalla de inicio de sesión, selecciona el perfil **Astronauta** en el selector y haz clic en **«Iniciar sesión»** (sin contraseña en entorno demo). Observa el estado inicial `LIVE MONITORING`.
   - Opcionalmente prueba el escenario didáctico (`Start scenario` -> `Next day` hasta día 5 -> `Reset`). El escenario está aislado por astronauta y marcado como `DEMO`.
   - En **Chequeo diario**, selecciona fatiga y ánimo, añade una nota y guarda: LÁTI muestra su orientación local inmediatamente debajo sin salir de la pantalla.
   - En **Registro real**, guarda 3 mediciones reales para construir tu línea base personal (`SUFFICIENT`) y luego una 4.ª medición con variación >= 20% para comprobar la generación automática de una alerta real explicable (no diagnóstica).
   - En **LÁTI**, prueba tanto mensajes escritos como el botón de micrófono (**Hablar**) para dictar en voz, verifica la indicación visual *Escuchando…*, escucha la respuesta hablada de LÁTI (con opción **Detener voz** o silenciar respuesta), revisa que mensajes de texto y voz permanecen en el historial y cambia entre inglés y español. Consulta además tus indicadores, línea base, chequeo o alertas abiertas.
   - En **Movimiento (Pose)** e **Imagen térmica**, verifica los controles y avisos honestos (sin simular inferencias si YOLO no está configurado ni simular temperatura central).
2. **Personal médico (`medic_demo`)**:
   - Entra en **Tripulación asignada**, selecciona `AST-001`, alterna entre **Registros reales** y **Demo ficticia**, y descarga el reporte CSV.
   - En **Alertas y seguimiento**, agrega una nota de seguimiento sobre la alerta real y confirma que pasa a estado `IN REVIEW` (`En revisión`).
3. **Administrador (`admin_demo`)**:
   - Confirma el distintivo `RBAC ISOLATED` (sin pestañas clínicas).
   - En **Administración**, crea un usuario astronauta de prueba (`AST-002`), gestiona asignaciones y consulta **Integraciones** (incluyendo estado real de **LÁTI · IA generativa** con verificación en vivo y verificación de NASA OSDR si hay acceso de red).
4. Cierra todas las sesiones con el botón de perfil antes de finalizar.

## Comprobaciones y límites

- Nunca incluyas claves reales en capturas, informes ni paquetes ZIP.
- El escenario demo de 5 días utiliza datos ficticios y nunca se mezcla con los registros reales en la línea base ni en los reportes reales.
- Si YOLO Pose no tiene dependencias/pesos instalados o no hay cámara conectada, la aplicación informa claramente la ausencia del servicio sin fabricar datos.

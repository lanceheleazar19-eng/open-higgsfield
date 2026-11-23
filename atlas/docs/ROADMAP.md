# Hoja de ruta

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Arquitectura, estructura, dashboard, configuración | ✅ Completada |
| 1.5 | ATLAS 2.0: centro de control holográfico | ✅ Completada |
| 2 | Cerebro IA: proveedores intercambiables (Ollama / Anthropic / OpenAI-compatible), chat con streaming, herramientas | ⏳ Siguiente |
| 3 | Memoria persistente (búsqueda, temporal/permanente, sin duplicados) | — |
| 4 | Gestor de tareas (prioridades, fechas, atrasos, objetivos, resúmenes) | — |
| 5 | Gimnasio (rutinas, series, RIR, volumen, progresión, estancamientos) | — |
| 6 | Finanzas (dinero real) y Trading (paper trading, separado) | — |
| 7 | Proyectos y negocios (espacio y memoria propios) | — |
| 8 | Calendario + Google Calendar | — |
| 9 | Voz (micrófono, TTS, palabra de activación, interrupción) | — |
| 10 | Automatizaciones, notificaciones, Daily Briefing | — |
| 11 | Seguridad, copias de seguridad, exportación, optimización | — |

## Fase 1 — entregado
- Backend FastAPI con configuración por entorno, SQLite + migraciones Alembic.
- Esquema base: tareas, eventos, movimientos (dinero real), sesiones de entreno,
  proyectos, ajustes, registro de actividad.
- `GET /api/dashboard`: agregación real (prioridades, atrasos, eventos en curso,
  mes financiero, actividad 7 días, proyectos con tareas abiertas).
- `GET/PUT /api/settings`: nombre, zona horaria, moneda (validados).
- `GET /api/system/health` y `/modules`: estado honesto (la IA aparece como no configurada).
- Interfaz: dashboard completo, barra lateral de 11 apartados (los no
  construidos indican su fase y no tienen botones falsos), configuración,
  responsive con menú móvil, estado “sin conexión”.
- 14 pruebas backend + 8 frontend.

Los módulos aún no construidos no tienen formularios: sus datos aparecerán en el
dashboard en cuanto su fase los permita registrar.

## ATLAS 2.0 — centro de control holográfico
- Núcleo 3D (three.js, cargado bajo demanda): esfera neuronal con sinapsis, anillos
  giroscópicos, órbitas, campo de partículas y líneas de energía con pulsos de datos.
- 10 módulos orbitando (Intelligence, Memory, Agents, Tasks, Calendar, Projects,
  Research, Fitness, Finance, Trading). Cada nodo es un botón con su cifra real; al pulsarlo
  abre su apartado. Al pasar el cursor el sistema se detiene y su conexión se ilumina.
- Estados del núcleo: en espera, escuchando, procesando y respondiendo, con onda expansiva al recibir una consulta.
- Lateral izquierdo: sistema, cerebro IA, memoria (registros, tamaño, disco), agentes, voz.
- Lateral derecho: reloj, alertas detectadas (reglas sobre datos reales), tareas, actividad.
- Barra de conversación: texto, micrófono (Web Speech API, Chrome/Edge), respuesta hablada
  activable, interrupción (Esc), resumen ejecutivo y comandos rápidos.
- Intérprete local `POST /api/assistant/query` y `GET /api/assistant/briefing`: responde con
  tus datos; para lo demás indica que el modelo de IA llega en la Fase 2.
- Sin WebGL hay una versión CSS; sin movimiento si el sistema pide «reducir movimiento»;
  el render se pausa fuera de pantalla.
- La telemetría detallada (paneles del dashboard original) sigue debajo del centro de control.

# Hoja de ruta

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Arquitectura, estructura, dashboard, configuración | ✅ Completada |
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

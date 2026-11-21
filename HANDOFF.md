# Registro de traspasos entre agentes

La entrada más nueva va arriba.

---

## 2026-11-21 · Claude · rama `claude/quirky-babbage-b5kmxc` (3)

**Hecho:** Nexo Core ahora habla y escucha. Usa la capacidad `tts`: botón de voz con 4 voces y botón para callar, lee las respuestas del chat y el análisis. Usa también `dictation`: botón de micrófono que envía el mensaje al parar. Preferencia guardada en `localStorage` (`nexo-core-voz`). Capacidades declaradas: sample, tts y dictation.

**Probado:** la página carga y el chat en modo básico responde sin errores. La voz y el micrófono solo funcionan dentro de claude.ai (Chrome o la app de escritorio) y no se han podido probar aquí.

---

## 2026-11-21 · Claude · rama `claude/quirky-babbage-b5kmxc` (2)

**Hecho:** `nexo-core/index.html`, un panel personal con IA (estilo del vídeo de referencia, diseño propio): anillo de recuperación calculado a partir de sueño, calidad, energía y estrés; registro diario; hábitos con hora (verde si están hechos, rojo si están pendientes y ya ha pasado la hora); historial de 14 días; patrones calculados en local; chat con Nexo y botón "Analizar con IA" (capacidad `sample`, herramientas registrar_dia, marcar_habito y crear_habito). Datos en `localStorage` (`nexo-core-v1`), con datos de ejemplo marcados y un botón para borrarlos.

**Probado:** se renderiza a 1200 px y a 400 px sin desbordes ni errores de consola, y el registro actualiza el anillo. El chat con IA no se ha podido probar fuera de claude.ai.

**Pendiente:** conectar una pulsera o el móvil (Health Connect / Apple Salud) para no meter los datos a mano; unir NEXO y Nexo Core en una sola app.

---

## 2026-11-21 · Claude · rama `claude/quirky-babbage-b5kmxc`

**Hecho:**
- NEXO (`asistente/index.html`): chat con IA (capacidad `sample` de claude.ai, con herramientas para crear, listar y borrar citas y abrir webs), agenda en `localStorage`, modo básico sin IA, dictado por voz (capacidad `dictation`), estilo cyberpunk original.
- Análisis de negocio en `founder/` (competencia de menús baratos) e `ideas/ebau/` (informe de la junta).
- `AGENTS.md` con las reglas para trabajar varios agentes juntos.

**Probado:** modo básico en Chromium sin errores de consola: crear, listar y borrar citas, enlaces y búsquedas. El chat con IA solo funciona dentro de claude.ai y no se ha podido probar fuera.

**Pendiente (ideas, el dueño decide):**
- Avisos cuando llega la hora de una cita.
- Voz de NEXO (capacidad `tts`).
- Mejorar la versión para móvil.
- Las citas no se sincronizan entre dispositivos (solo `localStorage`).

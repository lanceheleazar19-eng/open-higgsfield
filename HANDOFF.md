# Registro de traspasos entre agentes

La entrada más nueva va arriba.

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

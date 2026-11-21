# Instrucciones para agentes de código (Codex, Claude y otros)

Este repositorio lo usan varios asistentes de IA por turnos. El dueño del proyecto es quien decide qué se hace. Lee este archivo antes de tocar nada.

## Qué hay aquí

| Carpeta | Qué es |
| --- | --- |
| `src/`, `public/`, `scripts/` | **OpenHiggsfield**: estudio web de generación de imágenes y vídeo con IA (Next.js 16, React 19, CSS plano, Zustand, pnpm). Ver `README.md`. |
| `nexo-core/index.html` | **Nexo Core**: panel personal (recuperación, sueño, hábitos, patrones y chat con IA). Mismas reglas que NEXO; datos en `localStorage` (`nexo-core-v1`). |
| `asistente/index.html` | **NEXO**: asistente personal en una sola página HTML (chat con IA, agenda de citas, enlaces a webs). Estilo cyberpunk original. Se publica como Artifact de claude.ai. |
| `founder/` | Análisis de negocio de la idea actual (menús baratos): `idea.md`, `competitors.md`, `competitors.csv`. |
| `ideas/ebau/` | Idea anterior (pack para la EBAU) con el informe de la junta. Archivada, no borrar. |

## Reglas para trabajar juntos

1. **Cada agente trabaja en su propia rama.** Claude usa ramas `claude/...`. Codex: crea ramas `codex/...`. No hagas commits en la rama de otro agente.
2. **No reescribas el historial** (nada de `push --force` ni `rebase` sobre ramas compartidas).
3. **Antes de empezar**, lee `HANDOFF.md` para ver qué hizo el último agente y qué falta.
4. **Al terminar**, añade una entrada al principio de `HANDOFF.md`: fecha, rama, qué cambiaste, qué probaste y qué queda pendiente.
5. **Commits pequeños** con mensajes claros en español.

## Reglas de NEXO (`asistente/index.html`)

- Es un único archivo HTML autocontenido: nada de dependencias externas salvo Google Fonts.
- Es un personaje **original**. No copies nombres, imágenes ni frases de personajes de videojuegos o series (por ejemplo de Cyberpunk 2077 / Edgerunners).
- Colores: rosa `#FF2E7A`, menta `#2EF2B0` y fondo casi negro `#07070C`. Fuentes: Chakra Petch (títulos), Inter (texto), JetBrains Mono (datos).
- La IA del chat usa la capacidad `sample` de los Artifacts de claude.ai (`window.claude.use("sample")`). Fuera de claude.ai funciona en "modo básico" con reglas locales: no lo rompas.
- Las citas se guardan en `localStorage` (clave `nexo-citas-v1`). Envuelve siempre lectura y escritura en `try/catch`.
- Todo texto del usuario se pinta con `textContent`, nunca con `innerHTML`.

## Para probar NEXO

Abre `asistente/index.html` en un navegador y prueba en el chat: «cita con el dentista mañana a las 5», «¿qué tengo esta semana?», «llévame a Google», «borra el dentista».

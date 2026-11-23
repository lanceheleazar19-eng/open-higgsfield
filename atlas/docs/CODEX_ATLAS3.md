# Tarea para Codex: ATLAS 3.0 (diseño carmesí + perfil personal)

Lee primero `AGENTS.md` (reglas obligatorias) y `docs/ROADMAP.md`. Trabaja solo en `frontend/`
salvo que se indique. El backend de esta tarea YA está hecho y probado; no lo cambies.

Imagen de referencia: la adjunta (`referencia.png`). Acércate al máximo a su composición,
iluminación y estética. La paleta carmesí ya está aplicada en `frontend/src/styles/global.css`
(variables `--blue`, `--cyan`, etc. son ahora tonos rojos; mantén los nombres).

## Endpoints disponibles (ya funcionan)
- `GET/PUT /api/profile` → `{display_name, username, preferences, created_at, has_avatar, avatar_version}`
  (PUT acepta `display_name`, `username` (3-30, a-z0-9._-), `preferences`). `display_name` es el
  mismo nombre que usa el saludo (`/api/settings.user_name`).
- `POST /api/profile/avatar` (multipart, campo `file`, JPG/PNG/WEBP ≤ 10 MB) · `GET /api/profile/avatar`
  (WEBP 512×512, usar `?v=avatar_version` para refrescar caché) · `DELETE /api/profile/avatar`.
- `GET /api/system/metrics` → `{cpu_percent, ram_percent, ram_used_bytes, ram_total_bytes}` (reales).
- `/api/dashboard` → `finance.series` = neto acumulado por día del mes (`[{date, net_cents}]`).

## Qué construir
1. **Cabecera superior global** (en `components/Layout.tsx`): logo triangular rojo + «ATLAS / PERSONAL
   INTELLIGENCE SYSTEM» a la izquierda; al centro una píldora «● SISTEMA ACTIVO» (o «SIN CONEXIÓN»,
   según `health`); a la derecha fecha y hora (componente `Clock`) y el **avatar** del usuario
   (foto o iniciales). Pulsar el avatar → `/settings#perfil`. NO inventar clima: no mostrar temperatura.
2. **Barra lateral** siempre desplegada en escritorio (≥1100 px; ancho `--rail`), con el elemento activo
   resaltado en rojo como en la referencia. Debajo, panel **«ESTADO DEL SISTEMA»**: minigráfico de CPU
   (sondear `/api/system/metrics` cada 5 s, guardar las últimas 30 lecturas en memoria), CPU %, RAM %,
   «Modelo IA» (`health.ai.model` o «Modo local») y «Conexión» (Online/Offline). En móvil sigue siendo
   menú desplegable.
3. **Centro de control** (`pages/ControlCenter.tsx`): eliminar el panel izquierdo `SystemPanel`
   (su información pasa a la barra lateral / Configuración) y dejar: núcleo grande en el centro y
   columna derecha. Mantén el saludo con el nombre encima del núcleo.
4. **Núcleo 3D rojo** (`components/core/scene.ts`): cambiar los colores de `LOOKS` a rojos/carmesí
   (en espera rojo, escuchando rojo claro, procesando rojo intenso con chispas blancas, respondiendo
   rosado). Añadir una **plataforma holográfica** debajo del núcleo: 4-5 anillos planos concéntricos
   (`RingGeometry`, mezcla aditiva) a y≈-2.3 y un haz de luz vertical suave. El texto «ATLAS» del
   centro con aspecto metálico plateado y brillo rojo (CSS en `.core-name`).
5. **Nodos** (`components/core/AtlasCore.tsx` + CSS `.node*`): círculo oscuro con anillo rojo brillante,
   icono blanco, etiqueta en blanco y debajo una línea de estado con punto de color
   (verde = activo, naranja = en fase, rojo = alerta). Los datos siguen saliendo de `nodeInfo` (reales).
6. **Columna derecha** (`components/control/IntelPanel.tsx`), tarjetas con borde rojo fino y esquinas
   marcadas: «TAREAS PENDIENTES» (Ver todas →; casilla que completa la tarea de verdad con
   `api.completeTask`), «PRÓXIMOS EVENTOS», «OBJETIVOS» (los actuales), «RESUMEN FINANCIERO»
   (neto del mes grande, gráfico de área con `finance.series`, ingresos y gastos; si `has_data` es false,
   estado vacío) y «ACTIVIDAD RECIENTE». Si hay alertas, mostrarlas arriba.
7. **Consola inferior** (`components/control/CommandBar.tsx`): botón de micrófono circular rojo,
   onda animada mientras escucha, campo «Pregunta a ATLAS…», botón enviar; debajo, a la izquierda
   «● Escuchando…/En espera» y botones rápidos «Resumen diario», «¿Qué tengo pendiente?»,
   «Analizar mi progreso» (y los existentes). Conserva TODA la funcionalidad actual (voz, detener,
   respuesta hablada, transcripción, sugerencias de memoria, tareas, gimnasio).
8. **Perfil personal** en Configuración (`pages/Settings.tsx`, sección con `id="perfil"`): foto actual,
   botón «Subir foto» (`accept="image/jpeg,image/png,image/webp"`), **recortador circular** antes de
   guardar (canvas: arrastrar para encuadrar + deslizador de zoom, máscara circular, exportar 512×512),
   vista previa, Guardar / Cambiar / Eliminar (vuelve a las iniciales), nombre visible, nombre de usuario,
   fecha de creación del perfil y preferencias personales. Al guardar el nombre, el saludo y el avatar
   se actualizan sin recargar (añade `profile` y `reloadProfile` a `AtlasContext`).
   La foto NO se envía nunca a la IA ni a servicios externos.

## Reglas
- No inventar datos; estados vacíos si no hay datos. Nada de botones sin función.
- Responsive (móvil incluido), accesible (aria-label en botones de icono), `prefers-reduced-motion`.
- Al terminar: `cd frontend && npx tsc -b && npx vitest run` en verde (actualiza los tests que
  dependan de `SystemPanel` y añade tests del perfil y del recortador), y `npm run build`.

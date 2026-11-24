# Arquitectura de VISTAN

## Principios

1. **Local primero.** Datos en tu disco, servidor en `127.0.0.1`. Nada sale del
   ordenador salvo que configures un proveedor de IA externo.
2. **Datos reales, nunca inventados.** Toda cifra se calcula con consultas
   sobre lo registrado. Sin datos → estado vacío explícito.
3. **Modular.** Cada módulo = modelos + servicio + router + página. Añadir uno
   no obliga a tocar los demás.
4. **Crecer sin reconstruir.** El esquema evoluciona con migraciones Alembic;
   una prueba falla si un modelo cambia sin su migración.
5. **Acciones sensibles con autorización.** VISTAN nunca mueve dinero, ejecuta
   operaciones de trading reales ni comandos del sistema por su cuenta.

## Tecnologías elegidas

| Capa | Elección | Motivo |
|---|---|---|
| Backend | **Python 3.11+ / FastAPI** | El ecosistema de IA (Ollama, SDKs de Anthropic/OpenAI, lectura de PDF/Excel, pandas para análisis) es Python. FastAPI: tipado, validación con Pydantic, async para streaming del chat. |
| Base de datos | **SQLite (WAL)** → PostgreSQL | Cero instalación, un solo archivo fácil de respaldar. SQLAlchemy 2 permite pasar a PostgreSQL cambiando `ATLAS_DATABASE_URL`. |
| Migraciones | **Alembic** | Cada fase amplía tablas sin perder tus datos. |
| Frontend | **React 19 + TypeScript + Vite** | SPA rápida, tipada. Vite en lugar de Next.js: VISTAN es una app local de un usuario, no necesita SSR ni servidor Node en producción; FastAPI sirve el build estático → un solo proceso. |
| Estilos | CSS propio con variables | Control total del look holográfico, sin dependencias pesadas. Fuentes empaquetadas (funciona sin Internet). |
| 3D | **three.js** (sin React Three Fiber) | Una sola dependencia, cargada en un chunk aparte solo si hay WebGL. Los nodos son HTML proyectado con la misma matemática que la escena: texto nítido, accesibles y pulsables. |
| Voz | Web Speech API del navegador | Sin dependencias ni claves; Chrome/Edge. Whisper/TTS locales en la Fase 9. |
| Pruebas | pytest + Vitest + Testing Library + Playwright | Unidad, API, UI y verificación visual. |

### Descartado por ahora
- **Next.js**: añade un servidor Node que no aporta nada en uso local.
- **Electron**: el navegador basta; se puede empaquetar como PWA más adelante.
- **Docker obligatorio**: complica el arranque en Windows. Se añadirá como opción.

## Cerebro de IA (Fase 2) — diseño

```
           ┌──────────────┐
 Chat ───▶ │ Orquestador  │──▶ herramientas (tareas, finanzas, gym, memoria…)
           └──────┬───────┘        cada una lee SOLO datos registrados
                  │
          ┌───────▼────────┐
          │  LLMProvider   │  interfaz común: chat(messages, tools) → stream
          └───────┬────────┘
     ┌────────────┼─────────────┬───────────────┐
  Ollama      Anthropic      OpenAI-compatible   (otros)
  (local)     (Claude)       (OpenAI, Groq, LM Studio…)
```

- **Enrutado por tarea**: configuración tipo `chat → claude`, `privado → ollama:llama3.1`,
  `resumen → ollama:qwen2.5`. Si un proveedor falla, se usa el siguiente.
- **Tool use** en lugar de “meter todo en el prompt”: el modelo pide
  `gym.progression(ejercicio="press inclinado")` y responde con el resultado
  real. Así no inventa estadísticas.
- Claves vía `.env`; nunca se envían al frontend.

## Memoria (Fase 3)
Tabla `memories` (tipo, contenido, alcance global/proyecto, temporal o
permanente con caducidad, fuente, hash para evitar duplicados) + búsqueda
de texto completo (SQLite FTS5) y, opcionalmente, embeddings para búsqueda
semántica. Consultable, editable y borrable desde la interfaz.

## Autonomía (Fase 10)
Planificador interno (APScheduler) que ejecuta “vigilantes”: tareas atrasadas,
presupuesto superado, estancamiento en el gimnasio, Daily Briefing matinal.
Generan notificaciones; las acciones que proponen quedan pendientes de tu
aprobación.

## Seguridad (transversal, reforzada en Fase 11)
- Servidor solo en loopback; CORS limitado a la interfaz local.
- Secretos en `.env` (ignorado por git).
- Dinero real y capital de trading en tablas separadas.
- Sin ejecución de comandos ni acceso a archivos fuera de lo que subas.
- Registro de actividad (`activity_log`) como auditoría.
- Fase 11: copias de seguridad automáticas, exportación JSON/CSV, PIN de acceso opcional.

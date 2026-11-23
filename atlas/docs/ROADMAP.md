# Hoja de ruta

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Arquitectura, estructura, dashboard, configuración | ✅ Completada |
| 1.5 | ATLAS 2.0: centro de control holográfico | ✅ Completada |
| 2 | Cerebro IA con Ollama: conversación en streaming anclada a tus datos | ✅ Completada |
| 3 | Memoria persistente (búsqueda, temporal/permanente, sin duplicados) | ✅ Completada |
| 4 | Gestor de tareas y objetivos medibles (prioridades, fechas, atrasos, progreso) | ✅ Completada |
| 5A | Gimnasio (rutinas, series, RIR, volumen, progresión, estancamientos) | ✅ Completada |
| 5B | Nutrición con fotos (modelo de visión local), macros y recomendaciones | ✅ Completada |
| 6 | Finanzas (dinero real) y Trading (paper trading, separado) | — |
| 7 | Proyectos y negocios (espacio y memoria propios) | — |
| 8 | Calendario (iCloud) + Gmail importante | ✅ Completada |
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

## Fase 2 — cerebro de IA
- `atlas/brain/`: interfaz `LLMProvider` + proveedor **Ollama** (`/api/tags`, `/api/chat` en streaming).
  Añadir otro proveedor (Anthropic, OpenAI-compatible) = una clase nueva, sin tocar el resto.
- Orquestador: elige modelo (preferencia del usuario o automático: qwen2.5 → llama3.1 → …, descarta
  modelos de embeddings), construye el prompt de identidad de ATLAS y una **instantánea de tus datos
  reales** (importes y fechas ya formateados) en cada consulta. Reglas: no inventar cifras, separar
  dinero real y trading, no ejecutar acciones.
- `POST /api/assistant/chat` (NDJSON: status → delta* → done/error), con historial de la conversación.
- Si Ollama no responde o falla antes de contestar → responde el intérprete local (marcado «Modo local»).
- Interfaz: respuesta en streaming, botón Detener, etiqueta del modelo en cada respuesta, página
  «Inteligencia artificial» con estado y selector de modelo. El resumen ejecutivo lo redacta la IA.
- Pruebas con un servidor que imita el protocolo real de Ollama.

Pendiente para fases posteriores: uso de herramientas (crear tareas, etc.) con confirmación,
memoria entre sesiones (Fase 3), Internet y documentos (Investigación).

## Fase 3 — memoria persistente
- Tablas `memories`, `conversations`, `conversation_messages` + índices FTS5 (sin tildes, por prefijos).
- Recuerdos: preferencia, objetivo, decisión, dato, nota; permanentes o temporales (caducan solos:
  «esta semana», «hoy», «este mes»…). Duplicados detectados por huella normalizada y similitud.
- En la conversación: «recuerda que…» guarda (lo pide el usuario); «olvida que…» propone y pide
  confirmación; la IA **propone** recuerdos tras cada respuesta y solo se guardan si el usuario acepta.
- Cada consulta recibe: perfil (preferencias y objetivos), recuerdos temporales vigentes, recuerdos
  relevantes y fragmentos de conversaciones anteriores (con filtro «ayer», «la semana pasada», «el mes pasado»).
- Conversaciones guardadas; ATLAS retoma la última al volver a abrirse; «Nueva conversación».
- Página Memoria: buscar, filtrar, añadir, editar, hacer permanente, olvidar, limpiar caducados,
  exportar JSON; pestaña de conversaciones con búsqueda y borrado.
- Misión de ATLAS en su identidad: ayudar al usuario a alcanzar su potencial, conectando consejos con sus objetivos.

## Fase 4 — tareas y objetivos medibles
- Tareas: prioridad, fecha con hora o de día completo, categoría (#etiqueta), objetivo vinculado,
  recordatorio (aviso en pantalla + notificación del sistema mientras ATLAS está abierto).
- Lenguaje natural en español (sin IA): «apúntame llamar al gestor el viernes a las 10, es urgente»,
  «recuérdame comprar leche mañana», «he terminado lo del gestor» (pide confirmación).
- Página Tareas: alta rápida con vista previa de la interpretación, grupos (atrasadas, hoy, próximas,
  sin fecha), completar/reabrir, edición, filtros y resumen del día.
- Semana: plan automático (atrasado y con fecha primero, resto por prioridad, tope por día);
  «Aplicar plan» fija fechas solo a tareas sin fecha, con confirmación.
- Objetivos numéricos (subir o bajar: ahorro, peso, clientes…) o por hitos (tareas vinculadas).
  Cálculos reales: % de progreso, progreso esperado a hoy, ritmo (adelantado / en ritmo / por detrás /
  fuera de plazo), cantidad necesaria por semana, ritmo real y fecha proyectada. Historial de registros.
- Alertas de objetivos atrasados; objetivos (y plan semanal si se pide) en el contexto de la IA;
  modo local responde «¿cómo voy con mis objetivos?» y «organízame la semana».

## Fase 5A — gimnasio
- Biblioteca de ~50 ejercicios en español con alias («triceps v», «jalón», «bayesian»…) y peso por lado.
- Plantilla con la rutina real del usuario (sáb. pecho/hombro/tríceps, dom. espalda/bíceps/trapecio,
  mié. pecho/espalda, jue. brazos), importable en un clic; editor de rutinas.
- Registro serie a serie (reps, kg, RIR) o pegando el texto tal como se apunta
  («Inclinado 2 calentamiento 2x8 40kg», «Triceps v 40kg x 8-10 2 series»…), también desde el chat.
  El calentamiento se anota sin inventar pesos.
- Análisis: 1RM estimado (Epley), progresión con gráfico, volumen semanal por músculo (secundario = ½ serie,
  referencia orientativa 10-20), frecuencia, estancamientos (3 sesiones sin superar el mejor 1RM previo),
  comparación con la sesión anterior, entreno del día y siguiente.
- Objetivos que se actualizan solos: peso máximo, 1RM o repeticiones de un ejercicio, o número de entrenos.
- Medidas corporales (peso, grasa, cintura, pecho, brazo, muslo) con gráfico.
- La IA recibe el resumen del gimnasio cuando la pregunta lo requiere; el modo local responde
  «¿qué me toca hoy?», «¿cuánto he progresado en…?», «¿qué músculos trabajo menos?».

## Extras
- Pantalla de arranque con bienvenida hablada (resumen real del día). Los navegadores no permiten
  hablar sin interacción: el botón «Iniciar ATLAS» la proporciona. Desactivable en Configuración.
- App instalable en el móvil (manifest, iconos, modo pantalla completa, márgenes de la muesca) y guía
  de acceso seguro con Tailscale (HTTPS, sin exponer ATLAS a Internet).

## ATLAS 3.0 — identidad carmesí y perfil personal
- Nueva identidad visual (carmesí sobre negro) inspirada en la referencia: cabecera con estado real del
  sistema, fecha/hora y foto de perfil; barra lateral fija con «Estado del sistema» (CPU y RAM reales,
  modelo IA, conexión); núcleo neuronal rojo con plataforma holográfica; nodos con línea de estado;
  columna derecha (alertas, tareas que se pueden completar, eventos, objetivos, resumen financiero con
  gráfico real, actividad); consola inferior con micrófono, onda de voz y comandos rápidos.
- Sin clima: no hay fuente meteorológica conectada y no se inventa (pendiente de integración real).
- Configuración › Perfil personal: nombre visible (es el del saludo), usuario, preferencias, fecha de
  creación y foto con recortador circular (arrastrar + zoom). La foto se valida por su contenido,
  se re-codifica sin metadatos (EXIF/GPS), se guarda solo en `data/avatar.webp` y nunca se envía a la IA.

## Fase 5B — nutrición
- Base local de 103 alimentos comunes en España (valores medios por 100 g) + alimentos propios.
- Registro escribiendo («200 g de arroz, pechuga de pollo y una manzana») o desde el chat
  («he desayunado 2 huevos y una tostada»), con unidades, gramos y cantidades en palabras.
- Foto del plato: el modelo de visión LOCAL de Ollama (p. ej. qwen2.5vl:7b) identifica alimentos y
  estima gramos; ATLAS propone y el usuario revisa antes de guardar. La foto no se almacena.
  Las macros siempre se calculan en el servidor con la base de alimentos.
- Perfil nutricional y objetivos (Mifflin-St Jeor × actividad, ±kcal según objetivo, proteína por kg;
  usa el último peso de Gimnasio › Cuerpo). Totales del día, semana con línea de objetivo,
  recomendaciones (proteína restante con alimentos concretos, hidratos antes de entrenar, etc.).
- La IA recibe la nutrición de hoy y de la semana cuando la pregunta lo requiere.

## Fase 8 — integraciones (Gmail + calendario de iCloud)
- Configuración › Integraciones: conectar con contraseñas de aplicación (Google / Apple), guardadas en el
  Llavero del sistema (keyring; archivo 600 como respaldo). Desconectar borra las credenciales.
- Gmail (IMAP, solo lectura, no marca como leído): guarda remitente, asunto y un extracto de los correos
  recientes. Importantes = marca «Importante» de Gmail + reglas (pagos, estudios, citas…, descarta
  boletines/no-reply) + IA local para los dudosos. Se muestran en el centro de control y la bienvenida
  hablada los menciona SOLO si hay alguno. La IA los conoce cuando se pregunta por el correo.
- iCloud Calendar (CalDAV): importa −1/+60 días con recurrencias, actualiza y elimina lo borrado;
  página Calendario con eventos de iCloud y de ATLAS, aviso de solapes y creación de eventos
  (en iCloud solo con confirmación explícita).
- Sincronización automática cada 30 min mientras ATLAS está abierto (y botón «Sincronizar ahora»).

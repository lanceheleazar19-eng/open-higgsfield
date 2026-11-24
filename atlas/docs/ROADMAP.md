# Hoja de ruta

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Arquitectura, estructura, dashboard, configuración | ✅ Completada |
| 1.5 | VISTAN 2.0: centro de control holográfico | ✅ Completada |
| 2 | Cerebro IA con Ollama: conversación en streaming anclada a tus datos | ✅ Completada |
| 3 | Memoria persistente (búsqueda, temporal/permanente, sin duplicados) | ✅ Completada |
| 4 | Gestor de tareas y objetivos medibles (prioridades, fechas, atrasos, progreso) | ✅ Completada |
| 5A | Gimnasio (rutinas, series, RIR, volumen, progresión, estancamientos) | ✅ Completada |
| 5B | Nutrición con fotos (modelo de visión local), macros y recomendaciones | ✅ Completada |
| 6 | Finanzas (dinero real), Trading (paper trading, separado) y Apple Salud | ✅ Completada |
| 7 | Proyectos y negocios (espacio y memoria propios) | ✅ Completada (VISTAN 4.0) |
| 8 | Calendario (iCloud) + Gmail importante | ✅ Completada |
| 9 | Voz manos libres (palabra de activación, interrupción, conversación continua) | ✅ Completada |
| 10 | Automatizaciones, notificaciones, Daily Briefing | ✅ Completada (VISTAN 4.0) |
| 11 | Seguridad, copias de seguridad, exportación, optimización | ✅ Completada (VISTAN 4.0) |
| 4.0 | Multiagente, Second Brain + grafo, RAG, Research Engine, multi-modelo, Command Center | ✅ Completada |

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

## VISTAN 2.0 — centro de control holográfico
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
  modelos de embeddings), construye el prompt de identidad de VISTAN y una **instantánea de tus datos
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
- Conversaciones guardadas; VISTAN retoma la última al volver a abrirse; «Nueva conversación».
- Página Memoria: buscar, filtrar, añadir, editar, hacer permanente, olvidar, limpiar caducados,
  exportar JSON; pestaña de conversaciones con búsqueda y borrado.
- Misión de VISTAN en su identidad: ayudar al usuario a alcanzar su potencial, conectando consejos con sus objetivos.

## Fase 4 — tareas y objetivos medibles
- Tareas: prioridad, fecha con hora o de día completo, categoría (#etiqueta), objetivo vinculado,
  recordatorio (aviso en pantalla + notificación del sistema mientras VISTAN está abierto).
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
  hablar sin interacción: el botón «Iniciar VISTAN» la proporciona. Desactivable en Configuración.
- App instalable en el móvil (manifest, iconos, modo pantalla completa, márgenes de la muesca) y guía
  de acceso seguro con Tailscale (HTTPS, sin exponer VISTAN a Internet).

## VISTAN 3.0 — identidad carmesí y perfil personal
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
  estima gramos; VISTAN propone y el usuario revisa antes de guardar. La foto no se almacena.
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
  página Calendario con eventos de iCloud y de VISTAN, aviso de solapes y creación de eventos
  (en iCloud solo con confirmación explícita).
- Sincronización automática cada 30 min mientras VISTAN está abierto (y botón «Sincronizar ahora»).

## Fase 6 — finanzas, trading simulado y Apple Salud
- **Finanzas (dinero real)**: ingresos y gastos (formulario o chat: «he gastado 12,50 en comida»,
  «he cobrado 300 de nómina», con botón Deshacer), categorías automáticas, resumen mensual, tasa de
  ahorro, evolución de 6 meses y presupuestos por categoría con alertas al 80 % y al superarlos.
  VISTAN solo registra: nunca hace pagos, transferencias ni se conecta al banco.
- **Trading (SIMULACIÓN)**: tabla propia (`paper_trades`) separada del dinero real. Capital virtual,
  operaciones largo/corto con SL/TP (validados), R:B planificado, P&L, R múltiple, win rate, profit
  factor, expectativa, drawdown, curva de capital, estadísticas por estrategia y errores recurrentes.
  Ninguna conexión con brókers. Webhooks de TradingView aplazados: exigirían exponer VISTAN a internet.
- **Apple Salud**: un Atajo del iPhone envía pasos, sueño, kcal activas, distancia y peso a
  `/api/health/ingest` con la cabecera `X-Vistan-Token` (clave en el Llavero, regenerable). El peso se
  copia a medidas corporales (Gimnasio/Nutrición). Guía paso a paso en Gimnasio › Salud.
- La IA recibe finanzas, trading (marcado como simulado) y salud solo cuando la pregunta lo pide.

## Fase 9 — voz manos libres
- **«Oye VISTAN»** (opcional, por dispositivo): escucha en segundo plano mientras la pestaña está abierta y
  visible. «VISTAN, ¿qué tengo hoy?» en una sola frase, o «VISTAN» → pitido → tu pregunta. Lo dicho antes de
  la palabra de activación se descarta. Botón en el centro de control y en Configuración › Voz.
- **Interrupción por voz**: mientras VISTAN habla, «para», «calla» o «VISTAN, …» lo cortan. Filtro de eco para
  que no se interrumpa a sí mismo con su propia voz.
- **Conversación continua**: si preguntas por voz, responde en voz y vuelve a escuchar; si te callas, lo deja.
- **Órdenes locales** (sin IA): «repite», «más despacio», «más rápido», «eso es todo».
- Privacidad explicada en la interfaz: el reconocimiento lo hace el navegador (Chrome → Google,
  Safari → Apple). Reconocimiento 100 % local (Whisper) queda como mejora futura.

## VISTAN 4.0 — sistema operativo personal
- **VISTAN CORE + 9 agentes** (Research, Finance, Fitness, Trading, Business, Coding, Memory, Planning, Security):
  cada mensaje pasa por CORE, que elige hasta 3 agentes (colaboran compartiendo herramientas), ejecuta sus
  herramientas reales sobre tus datos (registradas con nivel READ/WRITE/EXECUTE/ADMIN) y entrega el contexto
  al modelo. Traza visible en el chat y en Agentes › Ejecuciones. Sin modelo de IA, resume los datos reunidos.
- **Second Brain**: documentos PDF/DOCX/TXT/MD/CSV/XLSX/imágenes (visión local)/webs/notas → texto → fragmentos →
  índice FTS5 + embeddings de Ollama si hay modelo de embeddings → recuperación híbrida con fuentes [n] en el chat.
  Grafo de conocimiento real (proyectos, recuerdos, decisiones, ideas, objetivos, tareas, documentos, investigaciones,
  conversaciones y entidades; aristas de pertenencia, relaciones manuales y menciones), con zoom, filtros, búsqueda,
  vista por proyecto y edición de relaciones. Importación/exportación Markdown estilo Obsidian ([[enlaces]]).
- **Research Engine**: subpreguntas → DuckDuckGo + Wikipedia → lectura de páginas → afirmaciones por fuente →
  informe con conclusiones citadas, contradicciones, «sin confirmar», fiabilidad por dominio y confianza global.
  Reanudable por pasos; «investiga …» desde el chat. Sin IA: informe extractivo honesto.
- **Multi-modelo**: Ollama + OpenAI + Anthropic + Gemini (streaming real). Model Router por tarea (chat, agentes,
  investigación, JSON) con privacidad (solo local / local primero / mejor calidad), límite mensual, precios para
  calcular coste y registro de cada llamada (latencia, errores, tokens). Keys en el Llavero; «Probar» lista los
  modelos reales del proveedor.
- **Workflows**: Daily Briefing (08:00), Weekly Review (domingo 20:00), Project Analysis, Research Workflow y editor
  de workflows propios por pasos; programación, reanudación y aprobación para los pasos EXECUTE.
- **Seguridad**: política por niveles, aprobaciones, registro de actividad, filtro de instrucciones maliciosas en
  documentos/webs, copia automática diaria y antes de cada migración, exportación JSON completa.
- **Proactividad** configurable (atrasos, fechas, proyectos estancados, objetivos sin progreso, gastos inusuales,
  pausa en el entreno) con qué/por qué/datos/recomendación. **Command Center**, **Analytics**, **paleta ⌘K**,
  notificaciones, núcleo 3D con estados reales (escuchando, razonando, ejecutando, investigando, hablando, error),
  consola minimizable, «Hola VISTAN» y activación por dos palmadas (local, experimental).
- Pendiente / no posible aún: app nativa de macOS con atajos globales (hoy: arranque automático en segundo plano con
  LaunchAgent + PWA); reconocimiento de voz 100 % local (Whisper); datos de mercado en vivo para el Trading Agent.

## VISTAN — rediseño evolutivo
- **Identidad**: ATLAS pasa a llamarse **VISTAN** en toda la interfaz, voz, respuestas, logotipo, iconos de la app y
  documentación. Por compatibilidad se mantienen los identificadores internos (carpeta `atlas/`, variables
  `ATLAS_*`, nombre del Llavero, LaunchAgent): así no se pierden claves guardadas ni el arranque automático.
  La palabra de activación es «Hola VISTAN» (también entiende «bistan», «vistán»…; «ATLAS» sigue funcionando).
- **Sistema solar**: VISTAN CORE en el centro y 12 planetas (Intelligence, Memory, Agents, Research, Projects,
  Tasks, Calendar, Automations, Fitness, Nutrition, Finance, Trading) en 4 órbitas coplanarias con distinta
  distancia y velocidad, disco orbital, enlaces reales entre módulos con partículas y conexiones al núcleo.
  Cámara: rueda = zoom, arrastrar = girar, clic = acercarse al planeta y ver su contexto (también en el panel
  derecho), doble clic o «Abrir» = ir al módulo, Esc / ⌖ = vista general. Los planetas nunca se solapan:
  relajación a lo largo de su órbita (probada en un ciclo orbital completo y 12 tamaños de pantalla) y etiquetas
  que buscan hueco (derecha, izquierda, abajo, arriba) o se ocultan hasta pasar el ratón.
- **Navegación** agrupada: Sistema, Inteligencia, Organización, Personal, Finanzas, Configuración.
- **Fitness › Físico**: fotos privadas (JPG/PNG/WEBP/HEIC → WEBP sin EXIF en `data/private/photos`, permisos 600,
  servidas solo por la API sin caché), fecha, pose, comentario, historial, comparador antes/después y análisis
  con IA bajo demanda (1 foto o comparación de 2) que valora la fiabilidad de la comparación, usa tu historial de
  entrenamiento y objetivos, y filtra cualquier cifra corporal (% de grasa, cm, kg) o comentario médico.
- **Nutrición › Fotos y asesor**: comidas con foto, descripción, fecha/hora y tipo; estimación por alimento (tabla
  de alimentos cuando se reconoce, «estimación del modelo» si no), calidad, preguntas cuando falta información,
  gramos editables y confirmación antes de registrar; editar/borrar. Asesor que analiza 14 días frente a tus
  objetivos y entrenamiento (con IA o, sin ella, con un análisis directo de los datos).
- **Progress**: peso, entreno, nutrición, objetivos y fotos con tendencias reales (regresión con mínimo de puntos y
  días, comparada con el ruido entre registros) y resumen generado por IA o determinista.
- **Privacidad de imágenes**: análisis local por defecto (Ollama). Solo si eliges un proveedor en la nube para
  «Imágenes» se envían fotos, y cada vez se pide consentimiento indicando proveedor y modelo.
- **VISTAN CORE**: el Fitness Agent consulta Progress, los análisis de físico y las comidas fotografiadas.

## VISTAN · centro de control a pantalla completa (HUD)
- La pantalla principal ocupa todo el monitor: **System telemetry** (izquierda), **VISTAN CORE** con el sistema
  solar y marco de visor (centro), **Intelligence data** (derecha) y una **franja inferior** con objetivos,
  proyectos, actividad del día y la consola de conversación. En el HUD el menú se convierte en un carril de iconos.
- Telemetría real desde `GET /api/telemetry`: CPU/RAM/swap/carga, proceso de VISTAN (RSS, hilos, uptime), base de
  datos y disco, modelo activo y privacidad, ping de Ollama y modelos cargados en memoria, latencia de cada llamada
  a modelos (última, media, máxima, errores, serie), actividad de memoria (incluidos los recuerdos que la IA ha
  usado), agentes y procesos en ejecución, estado de conexiones y un registro de eventos real con hora.
  Lo que no se puede medir se muestra como **N/D**; las gráficas solo usan muestras tomadas (nada interpolado).
- Widgets que se pueden ocultar, mostrar y reordenar (⚙ en cada panel; se guarda en el navegador).
- En pantallas pequeñas se reorganiza en columna: núcleo, consola, franja, inteligencia y telemetría.

## VISTAN · voz con VoiceStudio
- Integración con [VoiceStudio](https://github.com/debpalash/VoiceStudio) (app de voz neuronal local, API en
  `127.0.0.1:3900`). VISTAN no ejecuta sus modelos: el núcleo hace de puente (`GET /api/voicestudio/status`,
  `POST /api/voicestudio/speak`), así el iPhone también oye la voz generada en el Mac.
- Configuración → Voz → **Motor de voz**: navegador o VoiceStudio, elección de voz (incluidos tus perfiles
  clonados) y prueba. Si VoiceStudio no está abierto, cada frase se lee con la voz del navegador.
- Estado real en la telemetría del HUD (conectado + latencia + nº de voces, o «no abierto»).
- Variables: `ATLAS_VOICESTUDIO_URL` (por defecto local) y `ATLAS_VOICESTUDIO_API_KEY` (solo si está en otro
  equipo; la clave nunca viaja por HTTP sin cifrar fuera del propio equipo).
- Rendimiento: tiempo real de síntesis por frase (Configuración y telemetría); si una frase tarda más de 7 s,
  esa respuesta sigue con la voz del navegador; el modelo de voz se precarga al abrir VISTAN; los modelos de
  visión de Ollama se liberan al minuto para dejar memoria al chat y a la voz.

## VISTAN · modo llamada
- Botón de teléfono en la consola: pantalla completa tipo llamada con un orbe que refleja el estado real
  (escuchando / pensando / hablando / silenciado), subtítulos en vivo, silenciar, interrumpir y colgar.
- Conversación continua sin pulsar nada; tras un silencio el micrófono se vuelve a abrir mientras dure la llamada.
- Se interrumpe a VISTAN simplemente hablando (filtro de eco); «eso es todo» o Esc cuelgan.
- La voz cuenta como «hablando» desde que se encola, para no abrir el micrófono encima de VoiceStudio.

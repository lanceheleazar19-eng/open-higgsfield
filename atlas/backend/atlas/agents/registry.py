"""Agentes especializados: responsabilidades, herramientas y cuándo intervienen."""

import re
from dataclasses import dataclass, field


@dataclass
class Agent:
    id: str
    name: str
    role: str
    tools: list[str]
    keywords: str
    actions: list[str] = field(default_factory=list)
    limits: str = ""
    helpers: list[str] = field(default_factory=list)  # agentes a los que puede pedir ayuda (VISTAN CORE los añade)

    @property
    def rx(self) -> re.Pattern:
        return re.compile(self.keywords)


AGENTS: dict[str, Agent] = {a.id: a for a in [
    Agent("research", "Research Agent", "Investiga en internet y en tus documentos, compara fuentes y detecta contradicciones.",
          ["docs.search", "research.recent"],
          r"investig|busca informacion|fuentes|compara|que se sabe|estudio de mercado|informe sobre|documento|pdf|segun mis",
          ["research.start"], "Solo fuentes públicas que lee en el momento; indica fecha de consulta y confianza."),
    Agent("finance", "Wealth Agent", "Finanzas reales y patrimonio: gastos, ingresos, presupuestos, activos, pasivos y ahorro.",
          ["finance.summary", "finance.recent", "life.wealth"],
          r"dinero|gast|ahorr|ingres|presupuest|finanz|cobr|pagad|euros|nomina|me queda|permitir|comprar|suscripci|patrimonio|activo|pasivo|deuda|riqueza",
          ["finance.record"], "Nunca inventa movimientos ni hace pagos o transferencias."),
    Agent("fitness", "Fitness Agent", "Entrenamiento, progresión, nutrición, salud y objetivos físicos.",
          ["gym.snapshot", "nutrition.today", "health.week", "progress.trends", "physique.latest", "meals.photos"],
          r"entren|gimnasio|gym|rutina|musculo|volumen|series|progres|fuerza|press|curl|peso|kilos|comid|calori|proteina|"
          r"dieta|macro|suen|dormi|pasos|salud|cansad|descans|creatina|suplement|evoluc|fisico|cuerpo|foto|mejorando|avanz",
          ["gym.log", "meal.log"], "Solo datos registrados o que le des."),
    Agent("trading", "Trading Agent", "Analiza tus operaciones simuladas, estrategias, riesgo y errores.",
          ["trading.desk", "trading.stats"], r"trad|operaci|estrategia|win ?rate|stop|take profit|drawdown|capital virtual|paper|mercado|bolsa|cripto|forex|accion",
          [], "SIMULACIÓN únicamente (dinero virtual). Nunca ejecuta operaciones por su cuenta ni toca dinero real."),
    Agent("betting", "Betting Agent", "Analiza eventos deportivos, compara probabilidades y revisa tus pronósticos simulados.",
          ["betting.summary"], r"apuest|pronostic|cuota|partido|liga|futbol|baloncesto|nba|tenis|formula 1|f1|combinada|bankroll|brier",
          [], "SIMULACIÓN con dinero ficticio. Nunca promete ganancias ni recomienda perseguir pérdidas."),
    Agent("business", "Entrepreneur Agent", "Oportunidades de negocio, mercados, modelos, costes, márgenes, DAFO y lanzamientos.",
          ["life.opportunities", "projects.list", "docs.search", "research.recent"],
          r"negocio|tienda|producto|proveedor|cliente|venta|marketing|shopify|emprend|margen|precio|competencia|marca|startup|empresa|dafo|viabilidad|idea",
          ["research.start"], "Se basa en tus proyectos, documentos e investigaciones."),
    Agent("learning", "Learning Agent", "VISTAN ACADEMY (Academy Coordinator): cursos, repasos pendientes, dominio por evaluación, "
          "puntos débiles y qué estudiar; elige al profesor especializado adecuado.",
          ["life.learning", "academy.overview"], r"aprend|estudi|leccion|examen|test|asignatura|academia|curso|conocimiento|idioma|repasar",
          [], "El dominio se mide con evaluaciones, nunca por lecciones completadas."),
    Agent("leadership", "Leadership Agent", "Liderazgo, negociación, equipos, crisis y decisiones bajo presión (simulaciones).",
          ["life.simulations", "life.decisions"], r"lider|negoci|equipo|deleg|conflict|crisis|presion|inversor|dirigir|jefe",
          [], "Evalúa conversaciones concretas, no a la persona."),
    Agent("discipline", "Discipline Agent", "Hábitos, rutinas, rachas y compromisos: detecta incumplimientos y patrones.",
          ["life.discipline", "gym.snapshot"], r"habito|rutina|disciplin|racha|constancia|cumpl|compromiso|procrastin|distracc|leer|lectura",
          [], "Exigente y objetivo: solo con lo registrado."),
    Agent("communication", "Communication Agent", "Comunicación, escucha, oratoria, networking y relaciones profesionales.",
          ["life.simulations", "life.contacts"], r"comunic|hablar en publico|oratoria|escucha|networking|contacto|relacion profesional|empatia|vocabulario|correo",
          [], "Enseña a comunicar con claridad y respeto, nunca a manipular."),
    Agent("opportunity", "Opportunity Agent", "Radar de oportunidades: tendencias, problemas, modelos y mercados con fuentes.",
          ["life.radar", "life.opportunities", "research.recent"], r"oportunidad|tendencia|sector|nicho|mercado emergente|radar|necesidad",
          ["research.start"], "Muestra fuentes y fecha de consulta; nada se presenta como seguro."),
    Agent("decision", "Decision Agent", "Diario de decisiones: compara lo esperado con lo ocurrido, sesgos y errores repetidos.",
          ["life.decisions", "life.failures", "life.vision"], r"decisi|decid|sesgo|error|equivoc|fallo|lecci|arrepent|elegir|opcion",
          [], "No juzga: busca patrones para aprender."),
    Agent("innovation", "Innovation Agent", "Investiga tecnologías, propone y evalúa experimentos, analiza ideas y documenta descubrimientos.",
          ["lab.overview", "lab.experiments", "lab.discoveries", "lab.ideas", "research.recent"],
          r"innovaci|laboratorio|experiment|hipotesis|prototip|tecnologi|invent|patente|paper|publicacion cientific|robotic|cuantic|biotec|nanotec|futuro",
          ["research.start"], "Distingue hechos, hipótesis y predicciones; nunca afirma patentabilidad.",
          helpers=["research", "coding", "business", "planning", "memory"]),
    Agent("coding", "Coding Agent", "Diagnostica VISTAN: versión, estado de la IA y errores recientes.",
          ["system.diagnose"], r"codigo|error|bug|fallo|no funciona|diagnost|version|programa|actualiza|log",
          [], "Diagnóstico de solo lectura: no modifica el código."),
    Agent("memory", "Memory Agent", "Organiza tus recuerdos, notas, documentos y relaciones.",
          ["memory.search", "memory.stats"],
          r"recuerd|memoria|te dije|sabes de mi|que sabes|anot|notas|apunte|relacion|grafo|segundo cerebro|decidi|decision",
          ["memory.save"], "Solo lo que tú has guardado o aprobado."),
    Agent("planning", "Planning Agent", "Objetivos, proyectos, tareas, calendario y prioridades.",
          ["tasks.overview", "goals.snapshot", "life.goals", "calendar.upcoming", "insights.detect", "projects.list"],
          r"tarea|pendiente|plan|organiz|semana|hoy|mañana|calendario|evento|reunion|objetivo|meta|priorid|proyecto|horario|agenda",
          ["task.create"], ""),
    Agent("legal", "VISTAN LEGAL AGENT", "Investiga normativa en fuentes oficiales, analiza contratos, prepara borradores, gestiona "
          "expedientes, plazos, riesgos y obligaciones de cumplimiento. Información jurídica, no asesoramiento profesional.",
          ["legal.overview", "legal.obligations"],
          r"legal|ley\b|leyes|juridic|abogad|contrato|clausula|demanda|denuncia|multa|plazo legal|rgpd|lopd|lssi|aviso legal|"
          r"politica de privacidad|terminos y condiciones|despido|herencia|alquiler|fianza|reclamacion|expediente|normativa|cumplimiento",
          ["legal.research", "legal.analyze"], "No ejecuta acciones jurídicas externas, no inventa normas ni sentencias, no calcula plazos y "
          "no envía documentos a la nube sin tu autorización.", helpers=["research", "business", "finance", "memory", "planning", "security"]),
    Agent("security", "Security Agent", "Supervisa permisos, acciones sensibles, credenciales y copias de seguridad.",
          ["security.status"], r"segur|permiso|credencial|api key|clave|privacidad|copia de seguridad|backup|contraseña|hack",
          ["backup.create"], "Nunca muestra el valor de una credencial."),
]}

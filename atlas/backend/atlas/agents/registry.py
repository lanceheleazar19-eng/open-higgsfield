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

    @property
    def rx(self) -> re.Pattern:
        return re.compile(self.keywords)


AGENTS: dict[str, Agent] = {a.id: a for a in [
    Agent("research", "Research Agent", "Investiga en internet y en tus documentos, compara fuentes y detecta contradicciones.",
          ["docs.search", "research.recent"],
          r"investig|busca informacion|fuentes|compara|que se sabe|estudio de mercado|informe sobre|documento|pdf|segun mis",
          ["research.start"], "Solo fuentes públicas que lee en el momento; indica fecha de consulta y confianza."),
    Agent("finance", "Finance Agent", "Organiza tus finanzas reales: gastos, ingresos, presupuestos e informes.",
          ["finance.summary", "finance.recent"],
          r"dinero|gast|ahorr|ingres|presupuest|finanz|cobr|pagad|euros|nomina|me queda|permitir|comprar|suscripci",
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
    Agent("business", "Business Agent", "Negocios, tiendas online, productos, proveedores y estrategia comercial.",
          ["projects.list", "docs.search", "research.recent"],
          r"negocio|tienda|producto|proveedor|cliente|venta|marketing|shopify|emprend|margen|precio|competencia|marca|startup",
          ["research.start"], "Se basa en tus proyectos, documentos e investigaciones."),
    Agent("coding", "Coding Agent", "Diagnostica VISTAN: versión, estado de la IA y errores recientes.",
          ["system.diagnose"], r"codigo|error|bug|fallo|no funciona|diagnost|version|programa|actualiza|log",
          [], "Diagnóstico de solo lectura: no modifica el código."),
    Agent("memory", "Memory Agent", "Organiza tus recuerdos, notas, documentos y relaciones.",
          ["memory.search", "memory.stats"],
          r"recuerd|memoria|te dije|sabes de mi|que sabes|anot|notas|apunte|relacion|grafo|segundo cerebro|decidi|decision",
          ["memory.save"], "Solo lo que tú has guardado o aprobado."),
    Agent("planning", "Planning Agent", "Objetivos, proyectos, tareas, calendario y prioridades.",
          ["tasks.overview", "goals.snapshot", "calendar.upcoming", "insights.detect", "projects.list"],
          r"tarea|pendiente|plan|organiz|semana|hoy|mañana|calendario|evento|reunion|objetivo|meta|priorid|proyecto|horario|agenda",
          ["task.create"], ""),
    Agent("security", "Security Agent", "Supervisa permisos, acciones sensibles, credenciales y copias de seguridad.",
          ["security.status"], r"segur|permiso|credencial|api key|clave|privacidad|copia de seguridad|backup|contraseña|hack",
          ["backup.create"], "Nunca muestra el valor de una credencial."),
]}

"""Registro de módulos: fuente única de verdad sobre qué está construido.

El frontend lee esto para no mostrar como disponible algo que no existe.
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    phase: int
    status: str  # "active" | "planned"
    summary: str
    planned: list[str] = field(default_factory=list)


MODULES: list[Module] = [
    Module("dashboard", "Dashboard", 1, "active", "Centro de control con el estado del día."),
    Module("ai", "Inteligencia artificial", 2, "active",
           "Cerebro conversacional multi-modelo (Ollama local + APIs externas).",
           ["Conversación natural", "Proveedor intercambiable (Ollama, Anthropic, OpenAI…)",
            "Lectura de PDF, Excel e imágenes", "Investigación web", "Herramientas sobre tus datos"]),
    Module("tasks", "Tareas", 4, "active", "Tareas, prioridades, plan semanal y objetivos medibles.",
           ["Crear por texto o voz", "Prioridades y fechas límite", "Detección de atrasos",
            "Recordatorios", "Resúmenes diarios y semanales"]),
    Module("gym", "Gimnasio", 5, "active", "Entrenamiento, progresión y medidas físicas.",
           ["Rutinas y ejercicios", "Series, repeticiones, peso y RIR", "Volumen semanal",
            "Progresión de fuerza", "Detección de estancamientos"]),
    Module("nutrition", "Nutrición", 5, "active", "Comidas, macros y fotos del plato analizadas en local."),
    Module("progress", "Progress", 5, "active", "Fotos de físico, peso, entrenos, nutrición y tendencias reales."),
    Module("finance", "Finanzas", 6, "active", "Dinero real: ingresos, gastos y presupuestos.",
           ["Ingresos y gastos", "Categorías y presupuestos", "Ahorro y objetivos",
            "Alertas de gasto excesivo", "Informes y gráficos"]),
    Module("trading", "Trading", 6, "active", "Paper trading con capital virtual, separado del real.",
           ["Registro de operaciones simuladas", "SL / TP y R:B", "Win rate y P&L",
            "Análisis de estrategias y errores", "Curva de capital virtual"]),
    Module("projects", "Proyectos", 7, "active", "Workspaces: tareas, notas, documentos e investigaciones por proyecto.",
           ["Objetivos y tareas por proyecto", "Ideas y estudios de mercado",
            "Márgenes, ingresos y gastos", "Estrategias de marketing"]),
    Module("calendar", "Calendario", 8, "active", "Eventos, horarios y planificación semanal.",
           ["Crear y editar eventos", "Detección de conflictos", "Planificación semanal",
            "Integración con Google Calendar"]),
    Module("memory", "Memoria", 3, "active", "Memoria persistente consultable y editable.",
           ["Preferencias, objetivos y decisiones", "Temporal vs permanente",
            "Búsqueda en el historial", "Sin duplicados"]),
    Module("knowledge", "Conocimiento", 4, "active", "Segundo cerebro: documentos (RAG), grafo y Markdown."),
    Module("research", "Investigación", 4, "active", "Investigación web con fuentes, contradicciones y confianza."),
    Module("agents", "Agentes", 4, "active", "VISTAN CORE y agentes especializados con permisos y trazas."),
    Module("workflows", "Automatizaciones", 4, "active", "Daily Briefing, Weekly Review y workflows propios."),
    Module("reports", "Analytics", 4, "active", "Estadísticas de fitness, finanzas, trading y proyectos."),
    Module("command", "Command Center", 4, "active", "Estado real del núcleo, agentes, modelos y procesos."),
    Module("settings", "Configuración", 1, "active", "Perfil, zona horaria y estado del sistema."),
]


def modules_as_dicts() -> list[dict]:
    return [asdict(m) for m in MODULES]

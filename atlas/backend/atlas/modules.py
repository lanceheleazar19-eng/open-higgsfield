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
    Module("gym", "Gimnasio", 5, "planned", "Entrenamiento, progresión y medidas físicas.",
           ["Rutinas y ejercicios", "Series, repeticiones, peso y RIR", "Volumen semanal",
            "Progresión de fuerza", "Detección de estancamientos"]),
    Module("finance", "Finanzas", 6, "planned", "Dinero real: ingresos, gastos y presupuestos.",
           ["Ingresos y gastos", "Categorías y presupuestos", "Ahorro y objetivos",
            "Alertas de gasto excesivo", "Informes y gráficos"]),
    Module("trading", "Trading", 6, "planned", "Paper trading con capital virtual, separado del real.",
           ["Registro de operaciones simuladas", "SL / TP y R:B", "Win rate y P&L",
            "Análisis de estrategias y errores", "Preparado para TradingView / MT5 (solo lectura)"]),
    Module("projects", "Proyectos", 7, "planned", "Proyectos y negocios con memoria propia.",
           ["Objetivos y tareas por proyecto", "Ideas y estudios de mercado",
            "Márgenes, ingresos y gastos", "Estrategias de marketing"]),
    Module("calendar", "Calendario", 8, "planned", "Eventos, horarios y planificación semanal.",
           ["Crear y editar eventos", "Detección de conflictos", "Planificación semanal",
            "Integración con Google Calendar"]),
    Module("memory", "Memoria", 3, "active", "Memoria persistente consultable y editable.",
           ["Preferencias, objetivos y decisiones", "Temporal vs permanente",
            "Búsqueda en el historial", "Sin duplicados"]),
    Module("research", "Investigación", 2, "planned",
           "Investigación web y análisis de documentos con fuentes citadas.",
           ["Búsqueda en Internet", "Lectura de PDF, Excel e imágenes",
            "Comparación de información", "Informes con fuentes"]),
    Module("agents", "Agentes", 10, "planned",
           "Agentes autónomos que vigilan tus datos y proponen acciones.",
           ["Vigilantes de tareas, gastos y entrenos", "Daily Briefing automático",
            "Propuestas que requieren tu aprobación", "Registro de todo lo que hacen"]),
    Module("reports", "Informes", 10, "planned", "Daily Briefing e informes automáticos.",
           ["Daily Briefing matinal", "Análisis semanal", "Alertas proactivas"]),
    Module("settings", "Configuración", 1, "active", "Perfil, zona horaria y estado del sistema."),
]


def modules_as_dicts() -> list[dict]:
    return [asdict(m) for m in MODULES]

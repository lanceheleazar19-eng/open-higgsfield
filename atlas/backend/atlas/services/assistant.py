"""Intérprete local de consultas (sin modelo de IA).

Responde preguntas frecuentes usando EXCLUSIVAMENTE los datos agregados del
dashboard. En la Fase 2 este módulo pasa a ser una herramienta del orquestador
de IA; las respuestas a cualquier otra pregunta se indican honestamente como
no disponibles.
"""

import re
import unicodedata

PRIORITY_ES = {"low": "baja", "medium": "media", "high": "alta", "critical": "crítica"}


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _money(cents: int, currency: str) -> str:
    sign = "-" if cents < 0 else ""
    v = f"{abs(cents) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}{v} {'€' if currency == 'EUR' else currency}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _hhmm(iso: str) -> str:
    return iso[11:16]


def _day(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


# --- respuestas por intención -------------------------------------------------

def _pending(d: dict) -> str:
    t = d["tasks"]
    if not t["pending"]:
        return "No tienes tareas pendientes registradas."
    parts = [f"Tienes {_plural(t['pending'], 'tarea pendiente', 'tareas pendientes')}"]
    if t["overdue"]:
        parts.append(f"{_plural(t['overdue'], 'atrasada', 'atrasadas')}")
    if t["due_today"]:
        parts.append(f"{_plural(t['due_today'], 'vence', 'vencen')} hoy")
    head = ", ".join(parts) + "."
    items = "; ".join(
        f"{i['title']} ({PRIORITY_ES[i['priority']]}{', atrasada' if i['overdue'] else ''})"
        for i in t["items"][:4]
    )
    return f"{head} Lo más importante: {items}."


def _priorities(d: dict) -> str:
    top = [i for i in d["tasks"]["items"] if i["priority"] in ("critical", "high")]
    if not top:
        return "No hay tareas de prioridad alta o crítica abiertas."
    return "Prioritarias: " + "; ".join(f"{i['title']} ({PRIORITY_ES[i['priority']]})" for i in top) + "."


def _events(d: dict) -> str:
    ev = d["events"]["items"]
    if not ev:
        return "No tienes eventos próximos en el calendario."
    return "Próximos eventos: " + "; ".join(
        f"{e['title']} — {'ahora' if e['in_progress'] else _day(e['start_at']) + ' a las ' + _hhmm(e['start_at'])}"
        for e in ev[:4]
    ) + "."


def _finance(d: dict) -> str:
    f = d["finance"]
    if not f["has_data"]:
        return "Aún no hay movimientos de dinero real registrados, así que no puedo darte cifras."
    c = f["currency"]
    txt = (f"Este mes ({f['month']}): ingresos {_money(f['income_cents'], c)}, gastos "
           f"{_money(f['expense_cents'], c)}, neto {_money(f['net_cents'], c)}. "
           f"Saldo registrado: {_money(f['balance_cents'], c)}.")
    if f["top_expense_categories"]:
        top = f["top_expense_categories"][0]
        txt += f" Donde más gastas: {top['category']} ({_money(top['amount_cents'], c)})."
    return txt


def _fitness(d: dict) -> str:
    fit = d["fitness"]
    if not fit["last_session"]:
        return "No hay entrenamientos registrados todavía."
    last = fit["last_session"]
    return (f"En los últimos 7 días: {_plural(fit['sessions_7d'], 'sesión', 'sesiones')}, "
            f"{fit['minutes_7d']} min. Último entreno: {last['routine'] or 'sesión'} el {_day(last['date'] + 'T')}.")


def _projects(d: dict) -> str:
    p = d["projects"]
    if not p["items"]:
        return "No tienes proyectos activos registrados."
    return f"{_plural(p['active'], 'proyecto activo', 'proyectos activos')}: " + "; ".join(
        f"{i['name']} ({_plural(i['open_tasks'], 'tarea abierta', 'tareas abiertas')})" for i in p["items"]
    ) + "."


def briefing(d: dict) -> str:
    g = d["greeting"]
    salute = {"morning": "Buenos días", "afternoon": "Buenas tardes", "night": "Buenas noches"}[g["part_of_day"]]
    name = f", {g['name']}" if g["name"] else ""
    s = d["summary"]
    lines = [
        f"{salute}{name}. Resumen ejecutivo:",
        f"• Tareas: {_plural(s['pending_tasks'], 'pendiente', 'pendientes')}"
        + (f", {_plural(s['overdue_tasks'], 'atrasada', 'atrasadas')}" if s["overdue_tasks"] else "") + ".",
        f"• Agenda: {_plural(s['upcoming_events'], 'evento próximo', 'eventos próximos')}.",
        f"• Proyectos: {_plural(s['active_projects'], 'activo', 'activos')}.",
        f"• Entrenamiento: {_plural(s['sessions_7d'], 'sesión', 'sesiones')} en 7 días.",
    ]
    f = d["finance"]
    if f["has_data"]:
        lines.append(f"• Finanzas del mes: neto {_money(f['net_cents'], f['currency'])}.")
    else:
        lines.append("• Finanzas: sin movimientos registrados.")
    if d.get("alerts"):
        lines.append("Atención: " + " ".join(a["text"] for a in d["alerts"]))
    return "\n".join(lines)


HELP = ("Ahora mismo trabajo en modo local, sin modelo de IA (el cerebro llega en la Fase 2). "
        "Puedo responder con tus datos registrados: «¿qué tengo pendiente hoy?», «¿qué es prioritario?», "
        "«próximos eventos», «¿cuánto he gastado este mes?», «¿cómo voy en el gimnasio?», "
        "«proyectos activos» o «resumen ejecutivo». Y puedo recordar cosas: «recuerda que…».")

INTENTS: list[tuple[str, re.Pattern, object]] = [
    ("briefing", re.compile(r"\b(resumen|briefing|informe|buenos dias|buenas tardes|buenas noches|hola)\b"), briefing),
    ("priorities", re.compile(r"prioritari|urgent|importante"), _priorities),
    ("tasks", re.compile(r"pendient|tarea|que tengo|hacer hoy"), _pending),
    ("events", re.compile(r"evento|agenda|calendario|reunion|cita"), _events),
    ("finance", re.compile(r"gast|dinero|finanz|ahorr|saldo|ingres|presupuest"), _finance),
    ("fitness", re.compile(r"entren|gimnasio|\bgym\b|ejercicio|rutina"), _fitness),
    ("projects", re.compile(r"proyecto|negocio"), _projects),
    ("help", re.compile(r"ayuda|que puedes|como funcionas|comandos"), lambda _d: HELP),
]


_MEMORY_Q = re.compile(r"recuerdas|que (sabes|recuerdas) de mi|que decidimos|que hablamos|que te dije|memoria")


def _memory_answer(memory: dict | None) -> str:
    if not memory or not any(memory.values()):
        return "No tengo nada guardado sobre eso. Puedes decirme «recuerda que…» y lo guardaré."
    items = [f"{m['contenido']} ({m['guardado']})" for m in memory.get("relevante", []) + memory.get("perfil", [])][:5]
    convs = [f"{c['fecha']} — {c['quien']}: {c['texto'][:120]}" for c in memory.get("conversaciones", [])][:3]
    parts = []
    if items:
        parts.append("Esto es lo que tengo guardado: " + "; ".join(items) + ".")
    if convs:
        parts.append("De conversaciones anteriores: " + " | ".join(convs))
    return " ".join(parts) or "No encuentro nada relacionado en mi memoria."


def answer(text: str, d: dict, memory: dict | None = None) -> dict:
    q = _norm(text)
    if _MEMORY_Q.search(q):
        return {"intent": "memory", "reply": _memory_answer(memory), "mode": "local"}
    for name, pattern, fn in INTENTS:
        if pattern.search(q):
            return {"intent": name, "reply": fn(d), "mode": "local"}  # type: ignore[operator]
    return {
        "intent": "unknown",
        "mode": "local",
        "reply": "No puedo responder a eso todavía: no hay ningún modelo de IA conectado (Fase 2). " + HELP,
    }

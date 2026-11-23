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


def _goals(d: dict) -> str:
    gs = d.get("goal_snapshot") or []
    if not gs:
        return "No tienes objetivos medibles registrados. Créalos en Tareas > Objetivos y calcularé tu ritmo."
    parts = []
    for g in gs:
        txt = f"{g['objetivo']}: {g['progreso']} ({g['ritmo']})"
        if g.get("necesario_por_semana"):
            txt += f", necesitas {g['necesario_por_semana']} por semana"
        if g.get("fecha_proyectada_al_ritmo_actual"):
            txt += f", al ritmo actual lo lograrás el {g['fecha_proyectada_al_ritmo_actual']}"
        parts.append(txt)
    return "Tus objetivos: " + "; ".join(parts) + "."


DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _plan(d: dict) -> str:
    plan = d.get("week_plan")
    if not plan:
        return "No puedo organizar la semana ahora mismo."
    from datetime import date as _date
    lines = []
    for x in plan["days"]:
        if x["tasks"]:
            wd = DAYS_ES[_date.fromisoformat(x["date"]).weekday()]
            lines.append(f"{wd} {x['date'][8:10]}: " + ", ".join(t["title"] for t in x["tasks"]))
    if not lines:
        return "No tienes tareas abiertas para organizar esta semana."
    return "Así te organizo la semana: " + "; ".join(lines) + ". Puedes aplicarlo en Tareas > Semana."


def _gym(d: dict, q: str) -> str:
    g = d.get("gym")
    if not g:
        return "No tengo datos del gimnasio todavía. Importa tu rutina en Gimnasio > Rutinas y registra tus series."
    if re.search(r"toca hoy|que entreno|que me toca", q):
        nxt = g.get("proximo_entreno")
        extra = f" El próximo: {nxt['name']} el {nxt['weekday_name']}." if nxt and g["hoy"].startswith("descanso") else ""
        return f"Hoy toca: {g['hoy']}.{extra}"
    if re.search(r"menos|olvid|descuid", q):
        low = g.get("musculos_por_debajo_de_10_series") or []
        return ("Esta semana van por debajo de 10 series: " + ", ".join(low) + ".") if low else "Todos tus músculos principales están en 10 series o más esta semana."
    for p in g.get("progresion_por_ejercicio", []):
        name = _norm(p["ejercicio"])
        if any(w in q for w in name.split() if len(w) > 4):
            txt = f"{p['ejercicio']}: última sesión {p['ultima_sesion']}, mejor serie {p['mejor_serie']}, 1RM estimado {p['1rm_estimado']} kg"
            if p.get("cambio_1rm_desde"):
                txt += f" ({p['cambio_1rm_desde']})"
            if p.get("estancado"):
                txt += ". Parece estancado: prueba a variar repeticiones o descanso"
            return txt + "."
    vol = g.get("volumen_semanal_series_por_musculo", {})
    for label, n in vol.items():
        if _norm(label) in q:
            return f"Esta semana llevas {n:g} series efectivas de {label}."
    return "Gimnasio: hoy " + g["hoy"] + ". " + ", ".join(f"{k}: {v:g} series" for k, v in vol.items() if v) + "."


def welcome(d: dict) -> str:
    """Saludo breve para la pantalla de arranque (se lee en voz alta). Solo datos reales."""
    g = d["greeting"]
    salute = {"morning": "Buenos días", "afternoon": "Buenas tardes", "night": "Buenas noches"}[g["part_of_day"]]
    parts = [f"{salute}{', ' + g['name'] if g['name'] else ''}. Bienvenido de nuevo. Todos los sistemas están operativos."]
    t = d["tasks"]
    if t["pending"]:
        txt = f"Tienes {_plural(t['pending'], 'tarea pendiente', 'tareas pendientes')}"
        if t["overdue"]:
            txt += f", {_plural(t['overdue'], 'atrasada', 'atrasadas')}"
        elif t["due_today"]:
            txt += f", {_plural(t['due_today'], 'vence', 'vencen')} hoy"
        parts.append(txt + ".")
    else:
        parts.append("No tienes tareas pendientes.")
    routine = d["fitness"].get("today_routine")
    parts.append(f"Hoy toca entrenar {routine}." if routine else "Hoy no tienes entrenamiento programado.")
    ev = [e for e in d["events"]["items"] if not e["in_progress"]]
    if ev:
        parts.append(f"Tu próximo evento: {ev[0]['title']}, a las {_hhmm(ev[0]['start_at'])}.")
    behind = [x for x in d.get("goals", {}).get("items", []) if x["pace"] == "behind"]
    if behind:
        parts.append(f"Atención: el objetivo {behind[0]['title']} va por detrás del ritmo.")
    mails = d.get("important_emails") or []
    if mails:
        about = "; ".join(f"de {m['de']} sobre «{m['asunto']}»" for m in mails[:3])
        parts.append(f"Tienes {_plural(len(mails), 'correo importante', 'correos importantes')}: {about}.")
    parts.append("¿En qué te ayudo?")
    return " ".join(parts)


HELP = ("Ahora mismo trabajo en modo local, sin modelo de IA (el cerebro llega en la Fase 2). "
        "Puedo responder con tus datos registrados: «¿qué tengo pendiente hoy?», «¿qué es prioritario?», "
        "«próximos eventos», «¿cuánto he gastado este mes?», «¿cómo voy en el gimnasio?», "
        "«proyectos activos» o «resumen ejecutivo». Y puedo recordar cosas: «recuerda que…».")

INTENTS: list[tuple[str, re.Pattern, object]] = [
    ("briefing", re.compile(r"\b(resumen|briefing|informe|buenos dias|buenas tardes|buenas noches|hola)\b"), briefing),
    ("plan", re.compile(r"organiza|planifica|plan de la semana"), _plan),
    ("goals", re.compile(r"objetivo|meta|potencial|progreso"), _goals),
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
    if d.get("gym") and re.search(r"toca hoy|que entreno|progresad|mejorando|volumen|series de|musculos?|estanc", q):
        return {"intent": "gym", "reply": _gym(d, q), "mode": "local"}
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

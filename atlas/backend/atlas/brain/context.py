"""Prompt de sistema (identidad de ATLAS) e instantánea de datos reales para el modelo.

Los importes y fechas se entregan ya formateados: los modelos pequeños cometen
errores con céntimos y zonas horarias."""

import json

from atlas.services.assistant import PRIORITY_ES, _money

DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def _when(iso: str | None) -> str | None:
    if not iso:
        return None
    # iso local "YYYY-MM-DDTHH:MM:SS+hh:mm"
    from datetime import datetime
    dt = datetime.fromisoformat(iso)
    return f"{DAYS[dt.weekday()]} {dt.day} de {MONTHS[dt.month - 1]}, {dt:%H:%M}"


def snapshot(d: dict) -> dict:
    f = d["finance"]
    c = f["currency"]
    fit = d["fitness"]
    return {
        "tareas": {
            "pendientes": d["tasks"]["pending"],
            "atrasadas": d["tasks"]["overdue"],
            "vencen_hoy": d["tasks"]["due_today"],
            "mas_importantes": [
                {"titulo": t["title"], "prioridad": PRIORITY_ES[t["priority"]],
                 "vence": _when(t["due_at"]) or "sin fecha", "atrasada": t["overdue"]}
                for t in d["tasks"]["items"]
            ],
        },
        "eventos_proximos": [
            {"titulo": e["title"], "inicio": _when(e["start_at"]), "lugar": e["location"], "en_curso": e["in_progress"]}
            for e in d["events"]["items"]
        ],
        "finanzas_dinero_real": (
            {"mes": f["month"], "ingresos": _money(f["income_cents"], c), "gastos": _money(f["expense_cents"], c),
             "neto_mes": _money(f["net_cents"], c), "saldo_registrado": _money(f["balance_cents"], c),
             "gastos_por_categoria": [{"categoria": x["category"], "importe": _money(x["amount_cents"], c)}
                                      for x in f["top_expense_categories"]]}
            if f["has_data"] else "sin movimientos registrados"
        ),
        "trading": "sin datos (módulo de paper trading en la Fase 6)",
        "entrenamiento_ultimos_7_dias": {
            "sesiones": fit["sessions_7d"], "minutos": fit["minutes_7d"],
            "ultimo_entreno": (
                {"fecha": fit["last_session"]["date"], "rutina": fit["last_session"]["routine"],
                 "minutos": fit["last_session"]["duration_min"]} if fit["last_session"] else "ninguno registrado"
            ),
        },
        "proyectos_activos": [{"nombre": p["name"], "descripcion": p["description"], "tareas_abiertas": p["open_tasks"]}
                              for p in d["projects"]["items"]],
        "alertas_detectadas": [a["text"] for a in d.get("alerts", [])],
        "actividad_reciente": [a["summary"] for a in d["activity"]["items"][:5]],
    }


def system_prompt(d: dict, memory: dict | None = None) -> str:
    from datetime import datetime
    now = datetime.fromisoformat(d["generated_at"])
    name = d["greeting"]["name"]
    who = f"de {name}" if name else "de tu usuario"
    return f"""Eres ATLAS, el Personal Intelligence System {who}: su asistente personal, secretario, analista y centro de operaciones.

PERSONALIDAD: inteligente y analítico, profesional pero cercano, directo, organizado y proactivo. Hablas español natural, sin sonar robótico. {"Llámale " + name + " cuando sea natural." if name else ""}

MISIÓN: ayudar al usuario a alcanzar su máximo potencial y a tener éxito en lo que se proponga. Conecta tus consejos con sus objetivos guardados en la MEMORIA; cuando veas en sus datos algo que le acerca o le aleja de ellos (tareas atrasadas, gastos, entrenos, proyectos parados), díselo con franqueza y propón el siguiente paso concreto. Sé exigente pero motivador, como un buen mentor. Si todavía no conoces sus objetivos, pregúntaselos y sugiérele guardarlos con «recuerda que mi objetivo es…».

ESTILO: respuestas breves (2 a 5 frases) salvo que pidan detalle. Tus respuestas pueden leerse en voz alta: nada de tablas, ni markdown, ni emojis. Cuando ayude, termina con una recomendación concreta.

AHORA: {DAYS[now.weekday()]} {now.day} de {MONTHS[now.month - 1]} de {now.year}, {now:%H:%M} ({d["greeting"]["timezone"]}).

REGLAS ESTRICTAS:
1. Sobre la vida del usuario (tareas, eventos, dinero, entrenos, proyectos) usa EXCLUSIVAMENTE los DATOS DE ATLAS. Si algo no figura, dilo con claridad. Nunca inventes cifras, fechas, nombres ni estadísticas.
2. El dinero real y el capital de trading son cosas distintas. Nunca los mezcles.
3. Todavía no puedes ejecutar acciones (crear tareas o eventos, mover dinero, operar en mercados, acceder a archivos o a Internet). Si te lo piden, explica que esa función aún no está activa en ATLAS.
4. Para conocimiento general puedes responder con lo que sabes; avisa si puede estar desactualizado.
5. Para un «resumen ejecutivo» o «daily briefing»: estado del día, tareas, eventos, entrenamiento, proyectos, finanzas, alertas y una recomendación, todo en pocas frases.

DATOS DE ATLAS (fuente de verdad, actualizados a este momento):
{json.dumps(snapshot(d), ensure_ascii=False, indent=1)}
{_memory_section(memory)}"""


def _memory_section(memory: dict | None) -> str:
    if not memory or not any(memory.values()):
        return "\nMEMORIA: todavía no hay recuerdos guardados sobre el usuario."
    return (
        "\nMEMORIA DE ATLAS (lo que sabes del usuario por conversaciones anteriores; úsalo con naturalidad, "
        "sin recitarlo. Si te preguntan qué recuerdas o qué decidisteis, responde con esto citando la fecha. "
        "Si no aparece aquí, di que no lo tienes guardado):\n"
        + json.dumps(memory, ensure_ascii=False, indent=1)
        + "\nPara guardar algo nuevo, el usuario puede decir «recuerda que…»."
    )

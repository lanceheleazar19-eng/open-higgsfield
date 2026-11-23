"""Alertas e información detectada a partir de los datos agregados del dashboard.

Reglas deterministas sobre datos reales; nunca se generan avisos sin datos que los respalden.
"""

from datetime import datetime


def build_alerts(d: dict) -> list[dict]:
    alerts: list[dict] = []
    t = d["tasks"]
    if t["overdue"]:
        alerts.append({
            "level": "critical", "module": "tasks",
            "text": f"{t['overdue']} {'tarea atrasada' if t['overdue'] == 1 else 'tareas atrasadas'}.",
        })
    if t["due_today"]:
        alerts.append({
            "level": "warning", "module": "tasks",
            "text": f"{t['due_today']} {'tarea vence' if t['due_today'] == 1 else 'tareas vencen'} hoy.",
        })
    now = datetime.fromisoformat(d["generated_at"])
    for e in d["events"]["items"]:
        start = datetime.fromisoformat(e["start_at"])
        if e["in_progress"]:
            alerts.append({"level": "info", "module": "calendar", "text": f"En curso: {e['title']}."})
        elif (start - now).total_seconds() <= 2 * 3600:
            mins = max(1, int((start - now).total_seconds() // 60))
            alerts.append({"level": "warning", "module": "calendar",
                           "text": f"«{e['title']}» empieza en {mins} min."})
    f = d["finance"]
    if f["has_data"] and f["expense_cents"] > f["income_cents"]:
        alerts.append({"level": "warning", "module": "finance",
                       "text": "Este mes los gastos superan a los ingresos registrados."})
    fit = d["fitness"]
    if fit["last_session"] and fit["sessions_7d"] == 0:
        alerts.append({"level": "info", "module": "gym",
                       "text": f"Sin entrenos en 7 días (último: {fit['last_session']['date']})."})
    for g in d.get("goals", {}).get("items", []):
        if g["pace"] == "behind":
            need = g.get("required_per_week")
            extra = f" Necesitas {abs(need):g}{(' ' + g['unit']) if g.get('unit') else ''} por semana para llegar." if need else ""
            alerts.append({"level": "warning", "module": "goals", "text": f"Objetivo «{g['title']}» va por detrás del ritmo.{extra}"})
        elif g["pace"] == "overdue":
            alerts.append({"level": "critical", "module": "goals", "text": f"Objetivo «{g['title']}» ha superado su fecha límite."})
    return alerts

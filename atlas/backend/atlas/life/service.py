"""Lógica de VISTAN LIFE OS. Todo se calcula con datos registrados; cada indicador explica su fórmula.
No hay puntuaciones psicológicas ni «valor como persona»: solo indicadores observables."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas.models import (Goal, GoalProgress, HealthDay, LfAsset, LfAssessment, LfCommitment, LfContact, LfDecision, LfFailure,
                          LfHabit, LfHabitLog, LfLesson, LfNetWorth, LfOpportunity, LfSimulation, LfSubject, Task, Transaction,
                          WorkoutSession)

SUBJECTS = [("economia", "Economía"), ("finanzas", "Finanzas"), ("emprendimiento", "Emprendimiento"), ("marketing", "Marketing"),
            ("ventas", "Ventas"), ("negociacion", "Negociación"), ("psicologia", "Psicología"), ("filosofia", "Filosofía"),
            ("historia", "Historia"), ("geopolitica", "Geopolítica"), ("ia", "Inteligencia artificial"), ("programacion", "Programación"),
            ("tecnologia", "Tecnología"), ("liderazgo", "Liderazgo"), ("comunicacion", "Comunicación"), ("idiomas", "Idiomas")]

OPP_CRITERIA = {"pain": ("Intensidad del problema", 0.2), "market": ("Tamaño de mercado", 0.15), "competition": ("Competencia manejable", 0.15),
                "fit": ("Encaje con tus capacidades", 0.15), "capital": ("Poco capital necesario", 0.1), "speed": ("Rapidez para validar", 0.1),
                "risk": ("Riesgo bajo", 0.15)}


def ensure_subjects(db: Session) -> list[LfSubject]:
    have = {s.key for s in db.scalars(select(LfSubject))}
    for k, n in SUBJECTS:
        if k not in have:
            db.add(LfSubject(key=k, name=n, syllabus=[]))
    db.flush()
    return list(db.scalars(select(LfSubject).order_by(LfSubject.id)))


# ───────── Emprendimiento ─────────

def economics(e: dict) -> dict:
    """Unit economics a partir de TUS supuestos (siempre estimaciones, nunca datos confirmados)."""
    def f(k: str) -> float | None:
        v = e.get(k)
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None
    price, vc, fixed, units, inv = f("price"), f("unit_cost"), f("fixed_monthly"), f("units_month"), f("initial_investment")
    out: dict = {"basis": "estimación con tus supuestos", "inputs": {"price": price, "unit_cost": vc, "fixed_monthly": fixed,
                                                                      "units_month": units, "initial_investment": inv}}
    if price is None or vc is None:
        return out | {"note": "Indica al menos precio y coste unitario"}
    cm = price - vc
    out["contribution_margin"] = round(cm, 2)
    out["gross_margin_pct"] = round(cm / price * 100, 2) if price else None
    if fixed is not None:
        out["breakeven_units_month"] = round(fixed / cm, 1) if cm > 0 else None
    if units is not None:
        rev = price * units
        profit = cm * units - (fixed or 0)
        out |= {"revenue_month": round(rev, 2), "profit_month": round(profit, 2), "net_margin_pct": round(profit / rev * 100, 2) if rev else None,
                "revenue_year": round(rev * 12, 2), "profit_year": round(profit * 12, 2)}
        if inv:
            out["payback_months"] = round(inv / profit, 1) if profit > 0 else None
            out["roi_year_pct"] = round(profit * 12 / inv * 100, 1)
    return out


def opp_score(scores: dict) -> dict:
    vals = {k: scores.get(k) for k in OPP_CRITERIA if isinstance(scores.get(k), (int, float))}
    if not vals:
        return {"score": None, "rated": 0, "formula": "Media ponderada de los criterios que puntúes de 1 a 5"}
    w = sum(OPP_CRITERIA[k][1] for k in vals)
    s = sum(OPP_CRITERIA[k][1] * v for k, v in vals.items()) / w
    return {"score": round(s / 5 * 100), "rated": len(vals), "of": len(OPP_CRITERIA),
            "formula": "Media ponderada de tus puntuaciones (1-5) × 20. Pesos: " + ", ".join(f"{n} {int(p * 100)} %" for n, p in OPP_CRITERIA.values())}


# ───────── Patrimonio ─────────

def networth(db: Session) -> dict:
    items = list(db.scalars(select(LfAsset)))
    a = [x for x in items if x.side == "asset"]
    li = [x for x in items if x.side == "liability"]
    tot_a, tot_l = sum(x.value for x in a), sum(x.value for x in li)
    est = sum(x.value for x in a if x.basis == "estimated") - sum(x.value for x in li if x.basis == "estimated")

    def by(xs: list[LfAsset], attr: str) -> dict:
        d: dict[str, float] = defaultdict(float)
        for x in xs:
            d[getattr(x, attr)] += x.value
        return {k: round(v, 2) for k, v in d.items()}
    return {"assets": round(tot_a, 2), "liabilities": round(tot_l, 2), "net": round(tot_a - tot_l, 2), "estimated_part": round(est, 2),
            "personal_net": round(sum(x.value for x in a if x.scope == "personal") - sum(x.value for x in li if x.scope == "personal"), 2),
            "business_net": round(sum(x.value for x in a if x.scope == "business") - sum(x.value for x in li if x.scope == "business"), 2),
            "assets_by_category": by(a, "category"), "liabilities_by_category": by(li, "category"), "count": len(items)}


def snapshot_networth(db: Session, day: date) -> LfNetWorth:
    nw = networth(db)
    row = db.scalar(select(LfNetWorth).where(LfNetWorth.day == day)) or LfNetWorth(day=day)
    row.assets, row.liabilities, row.net, row.estimated_share = nw["assets"], nw["liabilities"], nw["net"], nw["estimated_part"]
    db.add(row)
    db.flush()
    return row


def savings_stats(db: Session, today: date, months: int = 6) -> dict:
    """Ahorro mensual real a partir de movimientos registrados (Finanzas)."""
    out = []
    y, m = today.year, today.month
    for _ in range(months):
        start = date(y, m, 1)
        end = date(y + (m == 12), m % 12 + 1, 1)
        inc = db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.kind == "income", Transaction.occurred_on >= start, Transaction.occurred_on < end)) or 0
        exp = db.scalar(select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.kind == "expense", Transaction.occurred_on >= start, Transaction.occurred_on < end)) or 0
        out.append({"month": f"{y}-{m:02d}", "income": inc / 100, "expense": exp / 100, "saved": (inc - exp) / 100,
                    "rate": round((inc - exp) / inc * 100, 1) if inc else None})
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return {"months": list(reversed(out)), "basis": "dinero real registrado en Finanzas"}


def simulate(start: float, monthly: float, annual_return_pct: float, years: int, inflation_pct: float = 0.0) -> dict:
    """Simulación (NO previsión): capital con aportación mensual y rentabilidad constante supuesta."""
    r = annual_return_pct / 100 / 12
    infl = inflation_pct / 100
    bal, contrib, rows = start, start, []
    for mth in range(1, years * 12 + 1):
        bal = bal * (1 + r) + monthly
        contrib += monthly
        if mth % 12 == 0:
            yr = mth // 12
            rows.append({"year": yr, "balance": round(bal, 2), "contributed": round(contrib, 2), "growth": round(bal - contrib, 2),
                         "real_balance": round(bal / (1 + infl) ** yr, 2)})
    return {"rows": rows, "final": rows[-1] if rows else None, "basis": "simulación con supuestos constantes; la realidad varía y puede haber pérdidas"}


# ───────── Academia ─────────

LEVELS = ["Sin evaluar", "Iniciación", "Básico", "Intermedio", "Avanzado", "Dominado"]


def mastery(db: Session, subject_id: int) -> dict:
    """Nivel de dominio SOLO por evaluaciones corregidas (no por lecciones completadas).
    Regla: media ponderada de las 6 últimas evaluaciones (exámenes ×2, dificultad pondera) → nivel;
    «Dominado» exige además un examen ≥ 85 % de dificultad ≥ 4."""
    ev = list(db.scalars(select(LfAssessment).where(LfAssessment.subject_id == subject_id, LfAssessment.score.is_not(None))
                         .order_by(LfAssessment.graded_at.desc()).limit(6)))
    lessons = db.scalar(select(func.count(LfLesson.id)).where(LfLesson.subject_id == subject_id, LfLesson.completed_at.is_not(None))) or 0
    if not ev:
        return {"level": 0, "label": LEVELS[0], "avg": None, "assessments": 0, "lessons_done": lessons,
                "rule": "Haz un test para medir tu nivel: las lecciones completadas no cuentan como dominio."}
    w = [(2 if a.kind == "exam" else 1) * (0.6 + 0.2 * a.difficulty) for a in ev]
    avg = sum(a.score * wi for a, wi in zip(ev, w)) / sum(w)
    hard = max((a.difficulty for a in ev), default=1)
    level = 1 if avg < 40 else 2 if avg < 60 else 3 if avg < 75 else 4
    if level == 4 and hard < 3:
        level = 3  # sin pruebas de dificultad media-alta no se pasa de intermedio
    if any(a.kind == "exam" and a.score >= 85 and a.difficulty >= 4 for a in ev) and avg >= 80:
        level = 5
    weak = Counter(t for a in ev for t in ((a.feedback or {}).get("weak_topics") or []))
    return {"level": level, "label": LEVELS[level], "avg": round(avg, 1), "assessments": len(ev), "max_difficulty": hard, "lessons_done": lessons,
            "weak_topics": [t for t, _ in weak.most_common(5)],
            "rule": "Media ponderada de tus 6 últimas evaluaciones (exámenes cuentan doble y la dificultad pondera). "
                    "Dominado: media ≥ 80 % y un examen ≥ 85 % de dificultad ≥ 4."}


# ───────── Disciplina ─────────

def _due(h: LfHabit, d: date) -> bool:
    return d.weekday() in (h.days or []) and d >= h.created_at.date()


def _met(h: LfHabit, v: float | None) -> bool | None:
    if v is None:
        return None if not h.limit else True
    if h.kind == "check":
        return v >= 1
    if h.target is None:
        return True
    return v <= h.target if h.limit else v >= h.target


def habit_stats(db: Session, h: LfHabit, today: date, days: int = 30) -> dict:
    logs = {lg.day: lg.value for lg in db.scalars(select(LfHabitLog).where(LfHabitLog.habit_id == h.id, LfHabitLog.day > today - timedelta(days=400)))}
    due_days = [today - timedelta(days=i) for i in range(days) if _due(h, today - timedelta(days=i))]
    past = [d for d in due_days if d < today]
    met = [d for d in past if _met(h, logs.get(d)) is True]
    streak = 0
    d = today if (_due(h, today) and _met(h, logs.get(today))) else today - timedelta(days=1)
    for _ in range(400):
        if not _due(h, d):
            d -= timedelta(days=1)
            continue
        if _met(h, logs.get(d)) is True and (d in logs or h.limit):
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    best = cur = 0
    for i in range(400, -1, -1):
        dd = today - timedelta(days=i)
        if not _due(h, dd) or dd > today:
            continue
        if _met(h, logs.get(dd)) is True and (dd in logs or h.limit):
            cur += 1
            best = max(best, cur)
        elif dd < today:
            cur = 0
    by_wd: dict[int, list[int]] = defaultdict(list)
    for d in past:
        by_wd[d.weekday()].append(1 if d in met else 0)
    return {"id": h.id, "due_today": _due(h, today), "done_today": _met(h, logs.get(today)) is True and today in logs,
            "today_value": logs.get(today), "compliance_30d": round(len(met) / len(past) * 100, 1) if past else None,
            "due_30d": len(past), "met_30d": len(met), "streak": streak, "best_streak": best,
            "weekday": {wd: round(sum(v) / len(v) * 100) for wd, v in by_wd.items()},
            "calendar": [{"day": (today - timedelta(days=i)).isoformat(), "due": _due(h, today - timedelta(days=i)),
                          "value": logs.get(today - timedelta(days=i)), "met": _met(h, logs.get(today - timedelta(days=i)))}
                         for i in range(27, -1, -1)]}


WD = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def discipline_report(db: Session, today: date) -> dict:
    habits = list(db.scalars(select(LfHabit).where(LfHabit.active.is_(True))))
    stats = [habit_stats(db, h, today) | {"name": h.name, "category": h.category} for h in habits]
    overdue = list(db.scalars(select(LfCommitment).where(LfCommitment.status == "open", LfCommitment.due < today)))
    closed = list(db.scalars(select(LfCommitment).where(LfCommitment.status.in_(("done", "missed")), LfCommitment.due > today - timedelta(days=90))))
    findings: list[str] = []
    for s in stats:
        if s["compliance_30d"] is not None and s["due_30d"] >= 6 and s["compliance_30d"] < 60:
            findings.append(f"«{s['name']}»: cumplido {s['met_30d']} de {s['due_30d']} días previstos ({s['compliance_30d']} %).")
        low = [(wd, v) for wd, v in s["weekday"].items() if v < 40]
        if low and s["due_30d"] >= 10:
            findings.append(f"«{s['name']}» falla sobre todo en: {', '.join(WD[wd] for wd, _ in sorted(low))}.")
    if overdue:
        findings.append(f"{len(overdue)} compromiso(s) vencidos sin cerrar: " + "; ".join(c.title for c in overdue[:5]) + ".")
    missed = [c for c in closed if c.status == "missed"]
    if len(closed) >= 4:
        findings.append(f"Compromisos de los últimos 90 días: {len(closed) - len(missed)} cumplidos y {len(missed)} incumplidos "
                        f"({round((len(closed) - len(missed)) / len(closed) * 100)} %).")
    # Datos automáticos de otros módulos (no se duplican: se leen)
    sleep = [h.sleep_hours for h in db.scalars(select(HealthDay).where(HealthDay.day > today - timedelta(days=7))) if h.sleep_hours]
    workouts = db.scalar(select(func.count(WorkoutSession.id)).where(WorkoutSession.performed_on > today - timedelta(days=7))) or 0
    return {"habits": stats, "overdue_commitments": [{"id": c.id, "title": c.title, "due": c.due.isoformat(), "period": c.period} for c in overdue],
            "commitment_rate_90d": round((len(closed) - len(missed)) / len(closed) * 100, 1) if closed else None,
            "findings": findings, "auto": {"sleep_avg_7d": round(sum(sleep) / len(sleep), 2) if sleep else None, "sleep_days": len(sleep),
                                           "workouts_7d": workouts, "sources": "Apple Salud (sueño) y Gimnasio (entrenos)"}}


# ───────── Objetivos ─────────

def horizon(g: Goal) -> str:
    if not g.deadline:
        return "sin fecha"
    days = (g.deadline - g.start_date).days
    return "1 mes" if days <= 45 else "3 meses" if days <= 120 else "6 meses" if days <= 240 else "1 año" if days <= 500 else "5 años" if days <= 2200 else "10 años"


def stalled_goals(db: Session, today: date, days: int = 14) -> list[dict]:
    out = []
    for g in db.scalars(select(Goal).where(Goal.status == "active")):
        last_p = db.scalar(select(func.max(GoalProgress.recorded_at)).where(GoalProgress.goal_id == g.id))
        last_t = db.scalar(select(func.max(Task.completed_at)).where(Task.goal_id == g.id))
        last = max([x for x in (last_p, last_t, g.created_at) if x])
        idle = (datetime.utcnow() - last).days
        if idle >= days:
            pending = db.scalar(select(func.count(Task.id)).where(Task.goal_id == g.id, Task.status == "pending")) or 0
            out.append({"id": g.id, "title": g.title, "idle_days": idle, "pending_tasks": pending, "horizon": horizon(g),
                        "deadline": g.deadline.isoformat() if g.deadline else None})
    return sorted(out, key=lambda x: -x["idle_days"])


# ───────── Decisiones y errores ─────────

def decision_calibration(db: Session) -> dict:
    rev = [d for d in db.scalars(select(LfDecision).where(LfDecision.outcome.is_not(None)))]
    if not rev:
        return {"reviewed": 0, "brier": None, "bins": [], "note": "Revisa decisiones pasadas para medir tu calibración"}
    pairs = [(d.confidence / 100, 1 if d.outcome in ("as_expected", "better") else 0) for d in rev]
    brier = sum((p - o) ** 2 for p, o in pairs) / len(pairs)
    bins = []
    for lo, hi in ((0, 50), (50, 70), (70, 85), (85, 101)):
        xs = [(p, o) for p, o in pairs if lo <= p * 100 < hi]
        if xs:
            bins.append({"range": f"{lo}-{min(hi, 100)} %", "n": len(xs), "confidence": round(sum(p for p, _ in xs) / len(xs) * 100),
                         "hit": round(sum(o for _, o in xs) / len(xs) * 100)})
    return {"reviewed": len(rev), "brier": round(brier, 3), "bins": bins,
            "worse": sum(1 for d in rev if d.outcome == "worse"), "as_expected": sum(1 for d in rev if d.outcome == "as_expected"),
            "better": sum(1 for d in rev if d.outcome == "better")}


def failure_patterns(db: Session) -> dict:
    fs = list(db.scalars(select(LfFailure)))
    tags = Counter(t.lower() for f in fs for t in (f.tags or []))
    kinds = Counter(f.kind for f in fs)
    return {"count": len(fs), "tags": tags.most_common(10), "kinds": dict(kinds),
            "repeated": [t for t, n in tags.items() if n >= 2]}


# ───────── Indicadores de crecimiento (observables) ─────────

def _weeks(today: date, n: int = 8) -> list[tuple[date, date]]:
    start = today - timedelta(days=today.weekday())
    return [(start - timedelta(weeks=i), start - timedelta(weeks=i) + timedelta(days=7)) for i in range(n - 1, -1, -1)]


def growth(db: Session, today: date) -> list[dict]:
    weeks = _weeks(today)
    lbl = [w[0].strftime("%d/%m") for w in weeks]
    areas: list[dict] = []

    def series(fn) -> list:  # noqa: ANN001
        return [fn(a, b) for a, b in weeks]

    habits = list(db.scalars(select(LfHabit)))
    logs = list(db.scalars(select(LfHabitLog).where(LfHabitLog.day >= weeks[0][0])))

    def compliance(a: date, b: date) -> float | None:
        due = met = 0
        for h in habits:
            for i in range((b - a).days):
                d = a + timedelta(days=i)
                if d >= today or not _due(h, d):
                    continue
                due += 1
                v = next((lg.value for lg in logs if lg.habit_id == h.id and lg.day == d), None)
                met += 1 if (_met(h, v) is True and (v is not None or h.limit)) else 0
        return round(met / due * 100, 1) if due else None

    def study_min(a: date, b: date) -> float:
        hs = {h.id for h in habits if h.category == "study"}
        return sum(lg.value for lg in logs if lg.habit_id in hs and a <= lg.day < b)

    def assessments(a: date, b: date) -> float | None:
        xs = [x.score for x in db.scalars(select(LfAssessment).where(LfAssessment.graded_at >= datetime.combine(a, datetime.min.time()),
                                                                      LfAssessment.graded_at < datetime.combine(b, datetime.min.time())))]
        return round(sum(xs) / len(xs), 1) if xs else None

    def tasks_done(a: date, b: date) -> int:
        return db.scalar(select(func.count(Task.id)).where(Task.completed_at >= datetime.combine(a, datetime.min.time()),
                                                           Task.completed_at < datetime.combine(b, datetime.min.time()))) or 0

    def workouts(a: date, b: date) -> int:
        return db.scalar(select(func.count(WorkoutSession.id)).where(WorkoutSession.performed_on >= a, WorkoutSession.performed_on < b)) or 0

    def sims(area: str):  # noqa: ANN202
        def f(a: date, b: date) -> int:
            return db.scalar(select(func.count(LfSimulation.id)).where(LfSimulation.area == area, LfSimulation.finished_at >= datetime.combine(a, datetime.min.time()),
                                                                     LfSimulation.finished_at < datetime.combine(b, datetime.min.time()))) or 0
        return f

    def opp_moves(a: date, b: date) -> int:
        return db.scalar(select(func.count(LfOpportunity.id)).where(LfOpportunity.updated_at >= datetime.combine(a, datetime.min.time()),
                                                                    LfOpportunity.updated_at < datetime.combine(b, datetime.min.time()))) or 0

    nw = list(db.scalars(select(LfNetWorth).order_by(LfNetWorth.day)))
    sv = savings_stats(db, today, 6)
    contacts = list(db.scalars(select(LfContact)))
    fu_due = [c for c in contacts if c.next_followup and c.next_followup < today]
    decided = db.scalar(select(func.count(LfDecision.id))) or 0
    cal = decision_calibration(db)
    goals = list(db.scalars(select(Goal).where(Goal.status == "active")))
    stalled = stalled_goals(db, today)
    sleep = [h.sleep_hours for h in db.scalars(select(HealthDay).where(HealthDay.day > today - timedelta(days=28))) if h.sleep_hours]
    subj = list(db.scalars(select(LfSubject)))
    mast = [mastery(db, s.id) for s in subj]
    evaluated = [m for m in mast if m["avg"] is not None]

    areas.append({"key": "entrepreneurship", "name": "Emprendimiento", "series": {"labels": lbl, "values": series(opp_moves), "unit": "oportunidades trabajadas"},
                  "indicators": [{"label": "Oportunidades activas", "value": db.scalar(select(func.count(LfOpportunity.id)).where(LfOpportunity.status.notin_(("discarded", "paused")))) or 0,
                                  "how": "Oportunidades que no están descartadas ni en pausa"},
                                 {"label": "En validación o más", "value": db.scalar(select(func.count(LfOpportunity.id)).where(LfOpportunity.status.in_(("validating", "building", "launched")))) or 0,
                                  "how": "Estado validando, construyendo o lanzada"}]})
    areas.append({"key": "finance", "name": "Finanzas", "series": {"labels": [m["month"] for m in sv["months"]], "values": [m["saved"] for m in sv["months"]], "unit": "€ ahorrados/mes (real)"},
                  "indicators": [{"label": "Patrimonio neto", "value": nw[-1].net if nw else None, "how": "Último registro de activos − pasivos (incluye estimaciones marcadas)"},
                                 {"label": "Tasa de ahorro (mes actual)", "value": sv["months"][-1]["rate"], "unit": "%", "how": "(ingresos − gastos) / ingresos registrados"}]})
    areas.append({"key": "knowledge", "name": "Conocimientos", "series": {"labels": lbl, "values": series(assessments), "unit": "nota media de evaluaciones"},
                  "indicators": [{"label": "Materias evaluadas", "value": len(evaluated), "how": "Materias con al menos una evaluación corregida"},
                                 {"label": "Nota media", "value": round(sum(m["avg"] for m in evaluated) / len(evaluated), 1) if evaluated else None, "unit": "%",
                                  "how": "Media del nivel de las materias evaluadas (solo evaluaciones)"}]})
    areas.append({"key": "leadership", "name": "Liderazgo", "series": {"labels": lbl, "values": series(sims("leadership")), "unit": "simulaciones completadas"},
                  "indicators": [{"label": "Simulaciones de liderazgo", "value": db.scalar(select(func.count(LfSimulation.id)).where(LfSimulation.area == "leadership", LfSimulation.status == "finished")) or 0,
                                  "how": "Escenarios terminados con informe de evaluación"}]})
    areas.append({"key": "discipline", "name": "Disciplina", "series": {"labels": lbl, "values": series(compliance), "unit": "% cumplimiento de hábitos"},
                  "indicators": [{"label": "Cumplimiento esta semana", "value": compliance(*weeks[-1]), "unit": "%", "how": "Días cumplidos / días previstos de tus hábitos activos"},
                                 {"label": "Minutos de estudio (semana)", "value": study_min(*weeks[-1]), "how": "Suma de hábitos de categoría estudio"}]})
    areas.append({"key": "communication", "name": "Comunicación", "series": {"labels": lbl, "values": series(sims("communication")), "unit": "simulaciones completadas"},
                  "indicators": [{"label": "Simulaciones de comunicación", "value": db.scalar(select(func.count(LfSimulation.id)).where(LfSimulation.area == "communication", LfSimulation.status == "finished")) or 0,
                                  "how": "Conversaciones simuladas terminadas"}]})
    areas.append({"key": "health", "name": "Salud", "series": {"labels": lbl, "values": series(workouts), "unit": "entrenamientos/semana"},
                  "indicators": [{"label": "Sueño medio (28 días)", "value": round(sum(sleep) / len(sleep), 2) if sleep else None, "unit": "h", "how": "Apple Salud (si está conectado)"}]})
    areas.append({"key": "goals", "name": "Objetivos", "series": {"labels": lbl, "values": series(tasks_done), "unit": "tareas completadas"},
                  "indicators": [{"label": "Objetivos activos", "value": len(goals), "how": "Objetivos en estado activo"},
                                 {"label": "Estancados (≥14 días sin avance)", "value": len(stalled), "how": "Sin progreso ni tareas completadas en 14 días"},
                                 {"label": "Decisiones registradas", "value": decided, "how": "Entradas del diario de decisiones"},
                                 {"label": "Calibración (Brier)", "value": cal["brier"], "how": "Confianza declarada frente a resultado real (0 = perfecto)"}]})
    areas.append({"key": "relationships", "name": "Relaciones", "series": None,
                  "indicators": [{"label": "Contactos", "value": len(contacts), "how": "Contactos registrados en el CRM"},
                                 {"label": "Seguimientos atrasados", "value": len(fu_due), "how": "Contactos con fecha de seguimiento pasada"}]})
    return areas


# ───────── Briefing, revisión semanal y recordatorios (integrados en Workflows) ─────────

def briefing_lines(db: Session, today: date) -> list[str]:
    lines: list[str] = []
    habits = [h for h in db.scalars(select(LfHabit).where(LfHabit.active.is_(True))) if _due(h, today)]
    if habits:
        done = {lg.habit_id for lg in db.scalars(select(LfHabitLog).where(LfHabitLog.day == today))}
        pend = [h.name for h in habits if h.id not in done and not h.limit]
        lines.append(f"• Hábitos de hoy: {len(habits)}" + (f"; pendientes: {', '.join(pend)}." if pend else "; todos registrados."))
    week_end = today + timedelta(days=7)
    cm = list(db.scalars(select(LfCommitment).where(LfCommitment.status == "open", LfCommitment.due <= week_end)))
    overdue = [c for c in cm if c.due < today]
    if cm:
        lines.append(f"• Compromisos abiertos hasta el {week_end:%d/%m}: {len(cm)}" + (f" ({len(overdue)} vencidos)." if overdue else "."))
    fu = list(db.scalars(select(LfContact).where(LfContact.next_followup <= today)))
    if fu:
        lines.append("• Seguimientos de contactos pendientes: " + ", ".join(c.name for c in fu[:5]) + ".")
    dr = list(db.scalars(select(LfDecision).where(LfDecision.review_on <= today, LfDecision.outcome.is_(None))))
    if dr:
        lines.append("• Decisiones listas para revisar: " + "; ".join(d.title for d in dr[:3]) + ".")
    st = stalled_goals(db, today)
    if st:
        lines.append("• Objetivos estancados: " + "; ".join(f"{g['title']} ({g['idle_days']} días)" for g in st[:3]) + ".")
    opps = list(db.scalars(select(LfOpportunity).where(LfOpportunity.status.in_(("research", "validating", "building")))))
    if opps:
        lines.append("• Negocios en marcha: " + "; ".join(f"{o.name} ({o.status})" for o in opps[:4]) + ".")
    return lines


def week_lines(db: Session, today: date) -> list[str]:
    since = today - timedelta(days=7)
    lines: list[str] = []
    habits = list(db.scalars(select(LfHabit).where(LfHabit.active.is_(True))))
    if habits:
        st = [habit_stats(db, h, today, 7) | {"name": h.name} for h in habits]
        kept = [s["name"] for s in st if s["compliance_30d"] is not None and s["compliance_30d"] >= 80]
        weak = [f"{s['name']} ({s['compliance_30d']} %)" for s in st if s["compliance_30d"] is not None and s["compliance_30d"] < 60]
        lines.append("• Hábitos mantenidos (≥80 %): " + (", ".join(kept) or "ninguno") + ("; por debajo del 60 %: " + ", ".join(weak) if weak else "") + ".")
    study = [h.id for h in habits if h.category == "study"]
    if study:
        mins = sum(lg.value for lg in db.scalars(select(LfHabitLog).where(LfHabitLog.habit_id.in_(study), LfHabitLog.day > since)))
        lines.append(f"• Estudio registrado: {mins:g} (unidad de tus hábitos de estudio).")
    ev = list(db.scalars(select(LfAssessment).where(LfAssessment.graded_at >= datetime.combine(since, datetime.min.time()))))
    if ev:
        lines.append(f"• Evaluaciones: {len(ev)}, nota media {sum(a.score for a in ev) / len(ev):.0f} %.")
    cms = list(db.scalars(select(LfCommitment).where(LfCommitment.due > since, LfCommitment.due <= today)))
    if cms:
        lines.append(f"• Compromisos de la semana: {sum(c.status == 'done' for c in cms)} cumplidos, {sum(c.status == 'missed' for c in cms)} incumplidos, "
                     f"{sum(c.status == 'open' for c in cms)} sin cerrar.")
    dec = list(db.scalars(select(LfDecision).where(LfDecision.day > since)))
    if dec:
        lines.append("• Decisiones tomadas: " + "; ".join(d.title for d in dec[:5]) + ".")
    fails = list(db.scalars(select(LfFailure).where(LfFailure.day > since)))
    if fails:
        lines.append("• Problemas/errores registrados: " + "; ".join(f.title for f in fails[:5]) + ".")
    sims = db.scalar(select(func.count(LfSimulation.id)).where(LfSimulation.finished_at >= datetime.combine(since, datetime.min.time()))) or 0
    if sims:
        lines.append(f"• Simulaciones de liderazgo/comunicación: {sims}.")
    st = stalled_goals(db, today)
    if st:
        lines.append("• A mejorar: objetivos sin avance — " + "; ".join(g["title"] for g in st[:3]) + ". Prioriza una acción concreta para cada uno.")
    return lines


def reminders(db: Session, now_local: datetime) -> int:
    """Notificaciones locales (una vez al día): hábitos a su hora sin registrar, seguimientos y revisiones de decisiones."""
    from atlas.security.policy import notify
    today = now_local.date()
    n = 0
    hhmm = now_local.strftime("%H:%M")
    logged = {lg.habit_id for lg in db.scalars(select(LfHabitLog).where(LfHabitLog.day == today))}
    for h in db.scalars(select(LfHabit).where(LfHabit.active.is_(True), LfHabit.remind_at.is_not(None))):
        if _due(h, today) and h.remind_at <= hhmm and h.reminded_on != today and h.id not in logged and not h.limit:
            notify(db, f"Hábito pendiente: {h.name}", "LIFE OS · Disciplina", "info", "/life?s=discipline")
            h.reminded_on = today
            n += 1
    if hhmm >= "09:00":
        for c in db.scalars(select(LfContact).where(LfContact.next_followup <= today)):
            if c.followup_notified != today:
                notify(db, f"Seguimiento pendiente: {c.name}", "LIFE OS · CRM (no se envía nada al contacto)", "info", "/life?s=crm")
                c.followup_notified = today
                n += 1
    db.flush()
    return n

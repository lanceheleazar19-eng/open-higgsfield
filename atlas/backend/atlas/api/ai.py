import json
import re

from sqlalchemy import select
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from atlas.api.deps import DB
from atlas.brain.orchestrator import brain_status, chat_events
from atlas.db import session_scope
from atlas.services import conversations as convs
from atlas.gym import service as gym_svc
from atlas.gym.parse import looks_like_log, parse_workout
from atlas.models import Exercise, Goal
from atlas.services import goals as goals_svc
from atlas.services import memory as mem
from atlas.services import tasks as tasks_svc
from atlas.services.clock import local_to_utc_naive
from atlas.services.nlp import TASK_TRIGGER, parse_complete_command, parse_task_command
from atlas.services.alerts import build_alerts
from atlas.services.dashboard import build_dashboard
from atlas.services.preferences import get_prefs

router = APIRouter(tags=["ai"])


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    # Solo se usa si no hay conversation_id (compatibilidad); si lo hay, el historial sale de la base de datos
    history: list[Message] = Field(default_factory=list, max_length=40)


@router.get("/api/ai/status")
def ai_status(db: DB) -> dict:
    return brain_status(get_prefs(db))


GYM_Q = re.compile(r"entren|gimnasio|gym|rutina|toca hoy|musculo|volumen|series|progres|mejorando|fuerza|press|curl|"
                   r"dominad|jalon|remo|triceps|biceps|pecho|espalda|hombro|pierna|1rm|estanc|peso|kilos|kg")
NUT_Q = re.compile(r"comid|comer|dieta|calori|kcal|proteina|macro|hidrat|grasa|nutric|desayun|cena|almuerz|merienda|volumen|engord|peso")
FIN_Q = re.compile(r"dinero|gast|ahorr|ingres|presupuest|finanz|cobr|pagad|euros|cuenta|nomina|me queda")
TRADE_Q = re.compile(r"trad|operacion|operaciones|estrategia|win ?rate|stop|take profit|drawdown|capital virtual|paper")
HEALTH_Q = re.compile(r"pasos|dormi|sueno|salud|cansad|descans|camin|kcal activas|pulsaciones")
PLAN_Q = re.compile(r"organiza|planifica|plan de la semana|mi semana|esta semana|que hago (esta|la) semana")
DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
PRIO_ES = {"low": "baja", "medium": "media", "high": "alta", "critical": "crítica"}


def _when(dt: datetime, all_day: bool) -> str:
    s = f"el {DAYS[dt.weekday()]} {dt.day}/{dt.month}"
    return s if all_day else f"{s} a las {dt:%H:%M}"


def _money_log(db, text: str, tz: str):  # noqa: ANN001
    """«he gastado 12,50 en comida» → registra un movimiento de DINERO REAL (solo apunte, nunca un pago)."""
    from atlas.finance import service as fin
    from atlas.models import Transaction
    p = fin.parse_money_command(text)
    if not p:
        return None
    t = Transaction(kind=p["kind"], amount_cents=p["amount_cents"], category=p["category"], description=p["description"],
                    occurred_on=datetime.now(ZoneInfo(tz)).date(), currency=str(get_prefs(db)["currency"]))
    db.add(t)
    db.commit()
    amount = f"{t.amount_cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    reply = f"Apuntado {'gasto' if t.kind == 'expense' else 'ingreso'} de {amount} € en «{t.category}»."
    if t.kind == "expense":
        today = t.occurred_on
        b = next((b for b in fin.budget_status(db, *fin.month_bounds(None, today)) if b["category"] == t.category), None)
        if b:
            reply += f" Llevas el {b['pct']} % del presupuesto de {t.category} este mes."
            if b["status"] == "over":
                reply += " ⚠️ Lo has superado."
    return {"type": "finance", "action": "logged", "transaction": fin.to_dict(t)}, reply


def _meal_log(db, text: str, tz: str):  # noqa: ANN001
    from atlas.models import Food
    from atlas.nutrition import service as nut
    now = datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    cmd = nut.parse_meal_command(text, now)
    if not cmd:
        return None
    meal, body = cmd
    items = nut.parse_meal_text(body, list(db.scalars(select(Food))))
    found = [(i["food"], i["grams"]) for i in items if i["food"]]
    missing = [i["name"] for i in items if not i["food"]]
    if not found:
        return ({"type": "meal", "action": "not_found", "entries": [], "missing": missing},
                "No reconozco esos alimentos. Añádelos en Nutrición > Alimentos o escríbelos de otra forma.")
    entries = nut.add_entries(db, now.date(), meal, found, "text")
    db.commit()
    tot = nut.day_totals(db, now.date())
    kcal = round(sum(e.kcal for e in entries))
    prot = round(sum(e.protein for e in entries))
    reply = f"Registrado en {meal}: " + ", ".join(f"{e.name} ({_es(e.grams)} g)" for e in entries) + f". {kcal} kcal y {prot} g de proteína."
    cfg = get_prefs(db).get("nutrition_profile")
    t = nut.compute_targets(cfg, nut.latest_weight(db)) if cfg else None
    if t:
        reply += f" Hoy llevas {tot['kcal']} de {t['kcal']} kcal y {round(tot['protein'])} de {t['protein']} g de proteína."
    if missing:
        reply += " No reconocí: " + ", ".join(missing) + "."
    return {"type": "meal", "action": "logged", "entries": [nut.entry_dict(e) for e in entries], "missing": missing}, reply


def _es(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _gym_log(db, text: str, tz: str):  # noqa: ANN001
    """Registra series si el mensaje es un entrenamiento. Devuelve (evento, respuesta) o None."""
    if not looks_like_log(text) or TASK_TRIGGER.match(text.strip()) or mem.parse_command(text):
        return None  # «apúntame…» es una tarea y «recuerda que…» es memoria, aunque mencionen series
    parsed = parse_workout(text, list(db.scalars(select(Exercise))))
    if not parsed:
        return None
    today = datetime.now(ZoneInfo(tz)).date()
    before = {g.id: g.current_value for g in goals_svc.active_goals(db)}
    s, _ = gym_svc.log_parsed(db, parsed, today)
    db.commit()
    lines = []
    for p in parsed:
        reps = "/".join(str(r) for r in p.reps)
        w = f" con {_es(p.weight)} kg{' por lado' if p.per_side else ''}" if p.weight else ""
        rir = f", RIR {p.rir}" if p.rir is not None else ""
        lines.append(f"{p.exercise_name}: {len(p.reps)}×({reps}){w}{rir}")
    reply = "Registrado en tu sesión de hoy: " + "; ".join(lines) + "."
    for g in goals_svc.active_goals(db):
        if g.auto_metric and before.get(g.id) != g.current_value:
            reply += f" Objetivo «{g.title}» actualizado: {_es(g.current_value)}{(' ' + g.unit) if g.unit else ''}."
    achieved = [g for g in db.scalars(select(Goal).where(Goal.status == "achieved", Goal.id.in_(list(before))))]
    for g in achieved:
        reply += f" 🎯 ¡Has conseguido «{g.title}»!"
    return {"type": "gym", "action": "logged", "session": gym_svc.session_dict(db, s)}, reply


def _task_command(db, text: str, tz: str):  # noqa: ANN001
    """Crea una tarea o propone completarla. Devuelve (evento, respuesta) o None."""
    now_local = datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    p = parse_task_command(text, now_local)
    if p:
        due = local_to_utc_naive(p.due.replace(tzinfo=ZoneInfo(tz))) if p.due else None
        reminder = due if (p.reminder and due) else None
        if p.reminder and p.all_day and due:  # recordatorio de día completo → a las 9:00 de ese día
            reminder = local_to_utc_naive(p.due.replace(hour=9, minute=0, second=0, tzinfo=ZoneInfo(tz)))
        t = tasks_svc.create_task(db, title=p.title, priority=p.priority, category=p.category,
                                  due_at=due, all_day=p.all_day, reminder_at=reminder)
        db.commit()
        reply = f"Apuntado: «{t.title}»"
        if p.due:
            reply += " para " + _when(p.due, p.all_day)
        if p.priority != "medium":
            reply += f", prioridad {PRIO_ES[p.priority]}"
        reply += "."
        if reminder:
            reply += " Te avisaré a su hora mientras ATLAS esté abierto."
        return {"type": "task", "action": "created", "task": tasks_svc.to_dict(t, tz)}, reply
    target = parse_complete_command(text)
    if target:
        t = tasks_svc.find_open_task(db, target)
        if not t:
            return {"type": "task", "action": "not_found", "task": None}, "No encuentro ninguna tarea abierta parecida."
        return ({"type": "task", "action": "complete_candidate", "task": tasks_svc.to_dict(t, tz)},
                f"¿Marco como hecha «{t.title}»? Confírmalo con el botón.")
    return None


def _line(ev: dict) -> str:
    return json.dumps(ev, ensure_ascii=False) + "\n"


@router.post("/api/assistant/chat")
def chat(body: ChatIn) -> StreamingResponse:
    """Conversación en streaming (NDJSON). Guarda la conversación y usa la memoria de ATLAS."""

    def gen():
        with session_scope() as db:
            prefs = get_prefs(db)
            tz = str(prefs["timezone"])
            conv = convs.get_or_create(db, body.conversation_id, body.text)
            hist = convs.history(db, conv) if body.conversation_id else [m.model_dump() for m in body.history]
            convs.add_message(db, conv, "user", body.text)
            db.commit()
            yield _line({"type": "meta", "conversation_id": conv.id})

            # Dinero real: «he gastado 12,50 en comida» / «he cobrado 300 de nómina»
            money_ev = _money_log(db, body.text, tz)
            if money_ev:
                ev, reply = money_ev
                yield _line(ev)
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "finance", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            # Registro de comidas: «he desayunado 2 huevos y una tostada»
            meal_ev = _meal_log(db, body.text, tz)
            if meal_ev:
                ev, reply = meal_ev
                yield _line(ev)
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "nutrition", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            # Registro de entrenamiento: «press inclinado 3x8 40kg rir 2»
            gym_ev = _gym_log(db, body.text, tz)
            if gym_ev:
                ev, reply = gym_ev
                yield _line(ev)
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "gym", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            # Órdenes de tareas: «apúntame…», «recuérdame…», «he terminado…»
            task_ev = _task_command(db, body.text, tz)
            if task_ev:
                ev, reply = task_ev
                yield _line(ev)
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "tasks", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            # Órdenes explícitas de memoria: «recuerda que…» / «olvida que…»
            cmd = mem.parse_command(body.text)
            if cmd:
                action, content = cmd
                if action == "remember":
                    m, created = mem.remember(db, content, kind=mem.guess_kind(content),
                                              expires_at=mem.guess_expiry(content, tz), source="chat")
                    item = mem.to_dict(m, tz)
                    yield _line({"type": "memory", "action": "saved" if created else "duplicate", "memory": item})
                    if created:
                        reply = f"Hecho. Lo recordaré: «{m.content}»."
                        if m.expires_at:
                            reply += f" Es temporal: lo tendré en cuenta hasta el {item['expires_at'][8:10]}/{item['expires_at'][5:7]}."
                    else:
                        reply = f"Eso ya lo tenía guardado: «{m.content}». He actualizado la fecha."
                else:
                    found = mem.search_memories(db, content, limit=1)
                    if found:
                        yield _line({"type": "memory", "action": "forget_candidate", "memory": mem.to_dict(found[0], tz)})
                        reply = f"¿Quieres que olvide esto?: «{found[0].content}». Confírmalo con el botón."
                    else:
                        reply = "No encuentro nada parecido en mi memoria."
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "memory", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            # Investigación en internet: «investiga …»
            from atlas.agents import core as agent_core
            rq = agent_core.research_command(body.text)
            if rq:
                from atlas.models import Research
                from atlas.research import engine as research_engine
                r = Research(question=rq, status="queued", state={})
                db.add(r)
                db.commit()
                research_engine.start(r.id)
                reply = (f"Empiezo a investigar «{rq}». Buscaré y leeré varias fuentes, compararé lo que dicen y te avisaré "
                         "al terminar con el informe, las fuentes y el nivel de confianza. Puedes seguirlo en Investigación.")
                yield _line({"type": "research", "research": research_engine.to_dict(r)})
                yield _line({"type": "delta", "text": reply})
                yield _line({"type": "done", "mode": "research", "model": None})
                convs.add_message(db, conv, "assistant", reply, mode="local")
                db.commit()
                return

            import time as _time
            t_start = _time.perf_counter()
            d = build_dashboard(db, prefs)
            d["alerts"] = build_alerts(d)
            # ATLAS CORE: elige agentes y ejecuta sus herramientas sobre los datos reales
            run_, actx = agent_core.run(db, body.text, prefs, tz)
            if run_.agents:
                d["agentes"] = actx
                yield _line({"type": "agents", "run": agent_core.run_dict(run_)})
            # RAG: fragmentos relevantes de tus documentos, con su fuente
            from atlas.knowledge.service import search as doc_search
            from atlas.models import Document
            if db.scalar(select(Document.id).limit(1)):
                docs = doc_search(db, body.text, k=5)
                if docs:
                    d["documentos"] = docs
                    yield _line({"type": "sources", "items": [{"n": i + 1, "document_id": x["document_id"], "title": x["title"],
                                                               "chunk": x["chunk"], "url": x["url"], "kind": x["kind"]}
                                                              for i, x in enumerate(docs)]})
            db.commit()
            d["goal_snapshot"] = goals_svc.snapshot(db, date.fromisoformat(d["generated_at"][:10]))
            if re.search(r"correo|email|mail|bandeja|mensaje", mem.normalize(body.text)):
                from atlas.integrations.email_sync import important_today
                d["important_emails"] = [{"de": m.sender, "asunto": m.subject, "motivo": m.reason, "extracto": m.snippet[:200]}
                                         for m in important_today(db, tz)] or "ninguno importante hoy (o Gmail no conectado)"
            if NUT_Q.search(mem.normalize(body.text)) or not brain_status(prefs)["configured"]:
                from atlas.nutrition import service as nut
                today = date.fromisoformat(d["generated_at"][:10])
                cfg = prefs.get("nutrition_profile")
                d["nutrition"] = {"hoy": nut.day_totals(db, today),
                                  "objetivos": nut.compute_targets(cfg, nut.latest_weight(db)) if cfg else "perfil nutricional sin completar",
                                  "ultimos_7_dias": nut.week_series(db, today)}
            if GYM_Q.search(mem.normalize(body.text)) or not brain_status(prefs)["configured"]:
                d["gym"] = gym_svc.snapshot(db, date.fromisoformat(d["generated_at"][:10]))
            if PLAN_Q.search(mem.normalize(body.text)) or not brain_status(prefs)["configured"]:
                d["week_plan"] = tasks_svc.plan_week(db, tz)
            q = mem.normalize(body.text)
            offline = not brain_status(prefs)["configured"]
            today_d = date.fromisoformat(d["generated_at"][:10])
            if FIN_Q.search(q) or offline:
                from atlas.finance import service as fin
                d["finanzas_dinero_real"] = fin.summary(db, today_d)
            if TRADE_Q.search(q) or offline:
                from atlas.trading import service as trd
                cap = prefs.get("paper_capital")
                st = trd.stats(db, float(cap) if cap else None)
                d["trading_SIMULADO"] = {k: v for k, v in st.items() if k != "curve"}
            if HEALTH_Q.search(q) or offline:
                from atlas.api.health import snapshot as health_snapshot
                d["apple_salud"] = health_snapshot(db, today_d)
            memory_ctx = mem.memory_context(db, body.text, tz, conversation_id=conv.id)
            db.commit()
            text, final = "", None
            for ev in chat_events(d, prefs, body.text, hist, memory=memory_ctx):
                if ev["type"] == "delta":
                    text += ev["text"]
                elif ev["type"] in ("done", "error"):
                    final = ev
                yield _line(ev)
            if text:
                mode = final.get("mode") if final and final["type"] == "done" else None
                convs.add_message(db, conv, "assistant", text, mode=mode, model=(final or {}).get("model"))
            agent_core.finish(db, run_, text, (final or {}).get("model"), t_start, ok=bool(text))
            db.commit()

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})
